"""
database.py
============
Couche d'accès aux données Redis (Upstash) pour l'application GestiStock.

Toute la logique Redis de l'application est centralisée ici dans la classe
RedisManager. Aucune commande Redis ne doit être exécutée en dehors de ce
fichier (contrainte imposée par le cahier des charges du module NoSQL).

Structures de données Redis utilisées :
    produit:<sku>        -> HASH   { nom, categorie, prix_unitaire, seuil_alerte, fournisseur }
    stock:<sku>           -> STRING (entier)
    historique:<sku>      -> LIST   [ JSON_mouvement, ... ]  (max 50, LTRIM)
    alertes:stock_bas     -> ZSET   { sku -> score = stock_actuel }
    stats:entrees:24h     -> STRING (compteur, TTL = 86400s)
    stats:sorties:24h     -> STRING (compteur, TTL = 86400s)

Auteur : Mouanga Gloire Distel (GROUPE 3 - GestiStock)
Module : NoSQL - Key-Value Store (Redis)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import redis
from dotenv import load_dotenv

# Chargement des variables d'environnement (.env local ou variables du
# tableau de bord Streamlit Cloud en production)
load_dotenv()

# --------------------------------------------------------------------------
# Constantes de configuration
# --------------------------------------------------------------------------
HISTORIQUE_MAX_LEN: int = 50          # Nombre max d'éléments conservés par LTRIM
HISTORIQUE_DISPLAY_LEN: int = 20      # Nombre d'éléments affichés dans l'UI
STATS_TTL_SECONDS: int = 86_400       # 24h
ALERTES_KEY: str = "alertes:stock_bas"
STATS_ENTREES_KEY: str = "stats:entrees:24h"
STATS_SORTIES_KEY: str = "stats:sorties:24h"

PRODUIT_FIELDS: tuple[str, ...] = (
    "nom",
    "categorie",
    "prix_unitaire",
    "seuil_alerte",
    "fournisseur",
)


class StockInsuffisantError(Exception):
    """Levée lorsqu'une sortie de stock dépasse la quantité disponible."""


class ProduitInexistantError(Exception):
    """Levée lorsqu'on tente d'opérer sur un SKU qui n'existe pas."""


class ProduitDejaExistantError(Exception):
    """Levée lorsqu'on tente de créer un produit avec un SKU déjà utilisé."""


class RedisManager:
    """
    Encapsule toutes les opérations Redis nécessaires à GestiStock.

    Cette classe est le point d'entrée unique vers Upstash Redis. Elle est
    instanciée une seule fois (via st.cache_resource côté app.py) et
    réutilisée dans toutes les pages Streamlit.
    """

    def __init__(self, redis_url: str | None = None) -> None:
        """
        Initialise le gestionnaire sans ouvrir immédiatement la connexion.

        Args:
            redis_url: URL de connexion Upstash. Si None, elle est lue
                depuis la variable d'environnement REDIS_URL.
        """
        self._redis_url = redis_url or os.getenv("REDIS_URL")
        self._client: redis.Redis | None = None

    # ------------------------------------------------------------------
    # Connexion
    # ------------------------------------------------------------------
    def connect(self) -> redis.Redis:
        """
        Établit (ou réutilise) la connexion au serveur Redis Upstash.

        Returns:
            Une instance redis.Redis prête à l'emploi (decode_responses=True).

        Raises:
            ValueError: si REDIS_URL n'est pas défini.
            redis.exceptions.ConnectionError: si la connexion échoue.
        """
        if self._client is not None:
            return self._client

        if not self._redis_url:
            raise ValueError(
                "REDIS_URL n'est pas défini. Vérifiez votre fichier .env "
                "ou les secrets Streamlit Cloud."
            )

        self._client = redis.from_url(
            self._redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        # Vérifie immédiatement que la connexion est fonctionnelle.
        self._client.ping()
        return self._client

    @property
    def client(self) -> redis.Redis:
        """Retourne le client Redis actif, en s'assurant qu'il est connecté."""
        return self.connect()

    # ------------------------------------------------------------------
    # Fonctionnalité 1 : Gestion des produits (HASH produit:<sku>)
    # ------------------------------------------------------------------
    def add_product(
        self,
        sku: str,
        nom: str,
        categorie: str,
        prix_unitaire: float,
        seuil_alerte: int,
        fournisseur: str,
        stock_initial: int = 0,
    ) -> None:
        """
        Crée un nouveau produit et initialise son stock.

        Args:
            sku: identifiant unique du produit (ex: SKU-001).
            nom: nom commercial du produit.
            categorie: catégorie du produit.
            prix_unitaire: prix unitaire de vente.
            seuil_alerte: seuil en dessous duquel une alerte est déclenchée.
            fournisseur: nom du fournisseur.
            stock_initial: quantité de stock de départ (0 par défaut).

        Raises:
            ProduitDejaExistantError: si le SKU existe déjà.
        """
        key = self._produit_key(sku)
        if self.client.exists(key):
            raise ProduitDejaExistantError(f"Le produit '{sku}' existe déjà.")

        mapping: dict[str, Any] = {
            "nom": nom,
            "categorie": categorie,
            "prix_unitaire": prix_unitaire,
            "seuil_alerte": seuil_alerte,
            "fournisseur": fournisseur,
        }
        self.client.hset(key, mapping=mapping)
        self.client.set(self._stock_key(sku), stock_initial)
        self.update_alerts(sku)

    def update_product(
        self,
        sku: str,
        nom: str | None = None,
        categorie: str | None = None,
        prix_unitaire: float | None = None,
        seuil_alerte: int | None = None,
        fournisseur: str | None = None,
    ) -> None:
        """
        Met à jour partiellement les champs d'un produit existant.

        Seuls les champs non None sont modifiés (mise à jour partielle).

        Raises:
            ProduitInexistantError: si le SKU n'existe pas.
        """
        key = self._produit_key(sku)
        if not self.client.exists(key):
            raise ProduitInexistantError(f"Le produit '{sku}' n'existe pas.")

        updates: dict[str, Any] = {}
        if nom is not None:
            updates["nom"] = nom
        if categorie is not None:
            updates["categorie"] = categorie
        if prix_unitaire is not None:
            updates["prix_unitaire"] = prix_unitaire
        if seuil_alerte is not None:
            updates["seuil_alerte"] = seuil_alerte
        if fournisseur is not None:
            updates["fournisseur"] = fournisseur

        if updates:
            self.client.hset(key, mapping=updates)
            # Le seuil ayant pu changer, on recalcule l'état d'alerte.
            self.update_alerts(sku)

    def delete_product(self, sku: str) -> None:
        """
        Supprime définitivement un produit et toutes ses clés associées :
        produit:<sku>, stock:<sku>, historique:<sku>, ainsi que son entrée
        dans le Sorted Set d'alertes.

        Raises:
            ProduitInexistantError: si le SKU n'existe pas.
        """
        key = self._produit_key(sku)
        if not self.client.exists(key):
            raise ProduitInexistantError(f"Le produit '{sku}' n'existe pas.")

        pipe = self.client.pipeline()
        pipe.delete(key)
        pipe.delete(self._stock_key(sku))
        pipe.delete(self._historique_key(sku))
        pipe.zrem(ALERTES_KEY, sku)
        pipe.execute()

    def get_product(self, sku: str) -> dict[str, Any] | None:
        """
        Récupère les informations d'un produit, enrichies de son stock actuel.

        Returns:
            Un dict avec les champs du produit + 'sku' + 'stock', ou None
            si le produit n'existe pas.
        """
        key = self._produit_key(sku)
        data = self.client.hgetall(key)
        if not data:
            return None

        data["sku"] = sku
        data["stock"] = self.get_stock(sku)
        # Normalisation des types numériques (Redis stocke tout en string).
        data["prix_unitaire"] = float(data.get("prix_unitaire", 0))
        data["seuil_alerte"] = int(float(data.get("seuil_alerte", 0)))
        return data

    def get_all_products(self) -> list[dict[str, Any]]:
        """
        Liste tous les produits avec leur stock actuel.

        Utilise SCAN (non bloquant) plutôt que KEYS pour rester safe en
        production sur un dataset volumineux.

        Returns:
            Liste de dicts triés par SKU.
        """
        produits: list[dict[str, Any]] = []
        for key in self.client.scan_iter(match="produit:*"):
            sku = key.split("produit:", 1)[1]
            produit = self.get_product(sku)
            if produit:
                produits.append(produit)
        return sorted(produits, key=lambda p: p["sku"])

    # ------------------------------------------------------------------
    # Fonctionnalité 2 : Gestion du stock (STRING stock:<sku>)
    # ------------------------------------------------------------------
    def get_stock(self, sku: str) -> int:
        """Retourne le stock actuel d'un produit (0 si la clé n'existe pas)."""
        valeur = self.client.get(self._stock_key(sku))
        return int(valeur) if valeur is not None else 0

    def add_stock(self, sku: str, quantite: int, commentaire: str = "") -> int:
        """
        Enregistre une entrée de stock (réception fournisseur) de façon
        atomique via INCRBY.

        Args:
            sku: identifiant du produit.
            quantite: quantité entrante (doit être > 0).
            commentaire: commentaire libre sur le mouvement.

        Returns:
            Le nouveau niveau de stock.

        Raises:
            ProduitInexistantError: si le SKU n'existe pas.
            ValueError: si la quantité n'est pas strictement positive.
        """
        if quantite <= 0:
            raise ValueError("La quantité d'entrée doit être strictement positive.")
        if not self.client.exists(self._produit_key(sku)):
            raise ProduitInexistantError(f"Le produit '{sku}' n'existe pas.")

        nouveau_stock = self.client.incrby(self._stock_key(sku), quantite)
        self.add_movement(sku, "entree", quantite, commentaire)
        self.update_alerts(sku)
        self._increment_daily_counter(STATS_ENTREES_KEY)
        return nouveau_stock

    def remove_stock(self, sku: str, quantite: int, commentaire: str = "") -> int:
        """
        Enregistre une sortie de stock (vente) de façon atomique via DECRBY,
        après vérification que le stock disponible est suffisant.

        Args:
            sku: identifiant du produit.
            quantite: quantité sortante (doit être > 0).
            commentaire: commentaire libre sur le mouvement.

        Returns:
            Le nouveau niveau de stock.

        Raises:
            ProduitInexistantError: si le SKU n'existe pas.
            ValueError: si la quantité n'est pas strictement positive.
            StockInsuffisantError: si le stock disponible est inférieur à
                la quantité demandée (le stock ne doit jamais être négatif).
        """
        if quantite <= 0:
            raise ValueError("La quantité de sortie doit être strictement positive.")
        if not self.client.exists(self._produit_key(sku)):
            raise ProduitInexistantError(f"Le produit '{sku}' n'existe pas.")

        stock_actuel = self.get_stock(sku)
        if stock_actuel < quantite:
            raise StockInsuffisantError(
                f"Stock insuffisant pour '{sku}' : disponible {stock_actuel}, "
                f"demandé {quantite}."
            )

        nouveau_stock = self.client.decrby(self._stock_key(sku), quantite)
        self.add_movement(sku, "sortie", quantite, commentaire)
        self.update_alerts(sku)
        self._increment_daily_counter(STATS_SORTIES_KEY)
        return nouveau_stock

    # ------------------------------------------------------------------
    # Fonctionnalité 3 : Historique des mouvements (LIST historique:<sku>)
    # ------------------------------------------------------------------
    def add_movement(
        self, sku: str, type_mouvement: str, quantite: int, commentaire: str = ""
    ) -> None:
        """
        Ajoute un mouvement en tête de l'historique du produit et tronque
        la liste aux HISTORIQUE_MAX_LEN éléments les plus récents (LTRIM).

        Args:
            sku: identifiant du produit.
            type_mouvement: "entree" ou "sortie".
            quantite: quantité concernée par le mouvement.
            commentaire: commentaire libre.
        """
        mouvement = {
            "type": type_mouvement,
            "quantite": quantite,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "commentaire": commentaire,
        }
        key = self._historique_key(sku)
        pipe = self.client.pipeline()
        pipe.lpush(key, json.dumps(mouvement, ensure_ascii=False))
        pipe.ltrim(key, 0, HISTORIQUE_MAX_LEN - 1)
        pipe.execute()

    def get_history(self, sku: str, limit: int = HISTORIQUE_DISPLAY_LEN) -> list[dict[str, Any]]:
        """
        Retourne les `limit` mouvements les plus récents d'un produit,
        du plus récent au plus ancien.

        Args:
            sku: identifiant du produit.
            limit: nombre de mouvements à retourner (20 par défaut).

        Returns:
            Liste de dicts {type, quantite, timestamp, commentaire}.
        """
        raw_items = self.client.lrange(self._historique_key(sku), 0, limit - 1)
        return [json.loads(item) for item in raw_items]

    # ------------------------------------------------------------------
    # Fonctionnalité 4 : Alertes de rupture (ZSET alertes:stock_bas)
    # ------------------------------------------------------------------
    def update_alerts(self, sku: str) -> None:
        """
        Met à jour la position du produit dans le Sorted Set d'alertes.

        Si le stock actuel est strictement inférieur au seuil d'alerte, le
        produit est ajouté/mis à jour dans alertes:stock_bas avec le stock
        actuel comme score. Sinon, il est retiré du Sorted Set.

        Args:
            sku: identifiant du produit à évaluer.
        """
        produit_key = self._produit_key(sku)
        seuil_raw = self.client.hget(produit_key, "seuil_alerte")
        if seuil_raw is None:
            # Produit inexistant : on s'assure qu'il n'est pas dans le ZSET.
            self.client.zrem(ALERTES_KEY, sku)
            return

        seuil_alerte = int(float(seuil_raw))
        stock_actuel = self.get_stock(sku)

        if stock_actuel < seuil_alerte:
            self.client.zadd(ALERTES_KEY, {sku: stock_actuel})
        else:
            self.client.zrem(ALERTES_KEY, sku)

    def get_alerts(self) -> list[dict[str, Any]]:
        """
        Retourne la liste des produits en alerte de stock, triés du plus
        urgent (stock le plus bas) au moins urgent.

        Returns:
            Liste de dicts {sku, nom, stock, seuil_alerte}.
        """
        # ZRANGE avec withscores=True trie déjà du score le plus bas au plus haut.
        entries = self.client.zrange(ALERTES_KEY, 0, -1, withscores=True)
        alertes: list[dict[str, Any]] = []
        for sku, score in entries:
            nom = self.client.hget(self._produit_key(sku), "nom") or sku
            seuil_raw = self.client.hget(self._produit_key(sku), "seuil_alerte")
            alertes.append(
                {
                    "sku": sku,
                    "nom": nom,
                    "stock": int(score),
                    "seuil_alerte": int(float(seuil_raw)) if seuil_raw else 0,
                }
            )
        return alertes

    # ------------------------------------------------------------------
    # Fonctionnalité 5 : Statistiques globales
    # ------------------------------------------------------------------
    def _increment_daily_counter(self, key: str) -> None:
        """
        Incrémente un compteur journalier et (re)pose son TTL à 24h.

        Utilise une pipeline pour garantir que l'incrément et l'expiration
        sont envoyés de façon groupée.
        """
        pipe = self.client.pipeline()
        pipe.incr(key)
        pipe.expire(key, STATS_TTL_SECONDS)
        pipe.execute()

    def get_statistics(self) -> dict[str, Any]:
        """
        Calcule et retourne les statistiques globales du tableau de bord.

        Returns:
            Dict contenant :
                - nb_produits_total
                - nb_produits_alerte
                - top3_stocks_faibles (liste de {sku, nom, stock})
                - entrees_24h
                - sorties_24h
        """
        produits = self.get_all_products()
        alertes = self.get_alerts()

        top3 = sorted(produits, key=lambda p: p["stock"])[:3]
        top3_simplifie = [
            {"sku": p["sku"], "nom": p["nom"], "stock": p["stock"]} for p in top3
        ]

        entrees_24h = self.client.get(STATS_ENTREES_KEY)
        sorties_24h = self.client.get(STATS_SORTIES_KEY)

        return {
            "nb_produits_total": len(produits),
            "nb_produits_alerte": len(alertes),
            "top3_stocks_faibles": top3_simplifie,
            "entrees_24h": int(entrees_24h) if entrees_24h else 0,
            "sorties_24h": int(sorties_24h) if sorties_24h else 0,
        }

    # ------------------------------------------------------------------
    # Utilitaires internes (construction des clés)
    # ------------------------------------------------------------------
    @staticmethod
    def _produit_key(sku: str) -> str:
        return f"produit:{sku}"

    @staticmethod
    def _stock_key(sku: str) -> str:
        return f"stock:{sku}"

    @staticmethod
    def _historique_key(sku: str) -> str:
        return f"historique:{sku}"
