"""
utils/helpers.py
=================
Fonctions utilitaires partagées entre les différentes pages Streamlit de
GestiStock. Ce module ne contient aucun appel Redis : uniquement du
formatage, de la validation et de petits calculs réutilisables.
"""

from __future__ import annotations

import random
import string
from datetime import datetime


def format_currency(montant: float, devise: str = "FCFA") -> str:
    """
    Formate un montant en chaîne lisible avec séparateur de milliers.

    Args:
        montant: montant numérique à formater.
        devise: symbole/code de la devise à afficher (FCFA par défaut,
            adapté au contexte congolais).

    Returns:
        Chaîne formatée, ex : "12 500 FCFA".

    Examples:
        >>> format_currency(12500)
        '12 500 FCFA'
        >>> format_currency(999.5)
        '999.50 FCFA'
    """
    if float(montant).is_integer():
        partie_entiere = f"{int(montant):,}".replace(",", " ")
        return f"{partie_entiere} {devise}"
    return f"{montant:,.2f} {devise}".replace(",", " ")


def format_timestamp(timestamp_iso: str, avec_heure: bool = True) -> str:
    """
    Convertit un timestamp ISO 8601 (tel que stocké par
    RedisManager.add_movement) en chaîne lisible au format français.

    Args:
        timestamp_iso: chaîne ISO 8601, ex "2026-07-10T14:32:00+00:00".
        avec_heure: si True, inclut l'heure (JJ/MM/AAAA HH:MM),
            sinon uniquement la date (JJ/MM/AAAA).

    Returns:
        Chaîne formatée, ou "Date inconnue" si le parsing échoue.
    """
    if not timestamp_iso:
        return "Date inconnue"
    try:
        dt = datetime.fromisoformat(timestamp_iso)
        return dt.strftime("%d/%m/%Y %H:%M") if avec_heure else dt.strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return timestamp_iso


def generate_sku(prefixe: str = "SKU", longueur_suffixe: int = 4) -> str:
    """
    Génère un SKU aléatoire suggéré, utile comme valeur par défaut dans un
    formulaire de création de produit (l'utilisateur reste libre de le
    modifier avant validation).

    Args:
        prefixe: préfixe du SKU généré.
        longueur_suffixe: nombre de caractères alphanumériques du suffixe.

    Returns:
        Une chaîne du type "SKU-A1B2".

    Examples:
        >>> len(generate_sku())
        8
    """
    caracteres = string.ascii_uppercase + string.digits
    suffixe = "".join(random.choices(caracteres, k=longueur_suffixe))
    return f"{prefixe}-{suffixe}"


def is_valid_sku(sku: str) -> bool:
    """
    Valide qu'un SKU respecte un format raisonnable : lettres, chiffres et
    tirets uniquement, sans espace, non vide.

    Args:
        sku: identifiant à valider.

    Returns:
        True si le format est valide, False sinon.

    Examples:
        >>> is_valid_sku("SKU-001")
        True
        >>> is_valid_sku("sku 001")
        False
    """
    sku = sku.strip()
    if not sku:
        return False
    autorises = set(string.ascii_letters + string.digits + "-_")
    return all(caractere in autorises for caractere in sku)


def stock_badge(stock: int, seuil: int) -> str:
    """
    Retourne un badge markdown coloré représentant l'état du stock par
    rapport au seuil d'alerte, réutilisé sur plusieurs pages (dashboard,
    produits, alertes) pour garder un affichage cohérent.

    Args:
        stock: stock actuel du produit.
        seuil: seuil d'alerte configuré pour le produit.

    Returns:
        Une chaîne markdown avec emoji, ex : "✅ OK", "🚨 Alerte".
    """
    if stock <= 0:
        return "🔴 Rupture"
    if stock < seuil:
        return "🚨 Alerte"
    return "✅ OK"


def truncate(texte: str, longueur_max: int = 60) -> str:
    """
    Tronque un texte à une longueur maximale en ajoutant une ellipse,
    utile pour l'affichage des commentaires de mouvements dans les tableaux.

    Args:
        texte: texte source.
        longueur_max: longueur maximale avant troncature.

    Returns:
        Le texte tronqué si nécessaire, inchangé sinon.

    Examples:
        >>> truncate("Livraison fournisseur du 10/07/2026", 15)
        'Livraison fo...'
    """
    texte = texte or ""
    if len(texte) <= longueur_max:
        return texte
    return texte[: longueur_max - 3].rstrip() + "..."
