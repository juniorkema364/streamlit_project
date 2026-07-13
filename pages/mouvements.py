"""
pages/mouvements.py
====================
Page "Mouvements" : enregistrement des entrées (réception fournisseur) et
des sorties (vente) de stock.

Les opérations passent exclusivement par manager.add_stock() et
manager.remove_stock(), qui utilisent respectivement INCRBY et DECRBY côté
Redis pour garantir l'atomicité, et refusent toute sortie qui rendrait le
stock négatif.
"""

from __future__ import annotations

import streamlit as st

from database import ProduitInexistantError, RedisManager, StockInsuffisantError


def render(manager: RedisManager) -> None:
    """
    Affiche la page Mouvements.

    Args:
        manager: instance RedisManager connectée, injectée par app.py.
    """
    st.title("🔁 Mouvements de stock")
    st.caption("Enregistrer une entrée (réception) ou une sortie (vente) de stock")

    try:
        produits = manager.get_all_products()
    except Exception as exc:  # noqa: BLE001
        st.error(f"❌ Erreur lors du chargement des produits : {exc}")
        return

    if not produits:
        st.info(
            "Aucun produit référencé. Rendez-vous sur la page **🗂️ Produits** "
            "pour en créer avant d'enregistrer un mouvement."
        )
        return

    tab_entree, tab_sortie = st.tabs(["⬆️ Entrée de stock", "⬇️ Sortie de stock"])

    with tab_entree:
        _render_entree(manager, produits)

    with tab_sortie:
        _render_sortie(manager, produits)


# --------------------------------------------------------------------------
# Onglet : Entrée de stock
# --------------------------------------------------------------------------
def _render_entree(manager: RedisManager, produits: list[dict]) -> None:
    st.subheader("⬆️ Enregistrer une entrée de stock")
    st.caption("Réception d'une commande fournisseur")

    options = {f"{p['nom']} ({p['sku']}) — stock actuel : {p['stock']}": p["sku"] for p in produits}

    with st.form("form_entree_stock", clear_on_submit=True):
        libelle = st.selectbox("Produit *", list(options.keys()), key="select_produit_entree")
        quantite = st.number_input("Quantité reçue *", min_value=1, step=1, value=1)
        commentaire = st.text_input(
            "Commentaire (optionnel)",
            placeholder="Ex : Livraison fournisseur du 10/07/2026, BL n°4521",
        )
        submitted = st.form_submit_button("Enregistrer l'entrée", type="primary")

    if not submitted:
        return

    sku = options[libelle]
    try:
        nouveau_stock = manager.add_stock(sku, int(quantite), commentaire.strip())
        st.success(
            f"✅ Entrée enregistrée : +{quantite} unité(s) pour « {sku} ». "
            f"Nouveau stock : **{nouveau_stock}**."
        )
        st.rerun()
    except ProduitInexistantError as exc:
        st.error(f"❌ {exc}")
    except ValueError as exc:
        st.error(f"❌ {exc}")
    except Exception as exc:  # noqa: BLE001
        st.error(f"❌ Erreur lors de l'enregistrement de l'entrée : {exc}")


# --------------------------------------------------------------------------
# Onglet : Sortie de stock
# --------------------------------------------------------------------------
def _render_sortie(manager: RedisManager, produits: list[dict]) -> None:
    st.subheader("⬇️ Enregistrer une sortie de stock")
    st.caption("Vente ou retrait de marchandise")

    options = {f"{p['nom']} ({p['sku']}) — stock actuel : {p['stock']}": p["sku"] for p in produits}

    with st.form("form_sortie_stock", clear_on_submit=True):
        libelle = st.selectbox("Produit *", list(options.keys()), key="select_produit_sortie")
        quantite = st.number_input("Quantité vendue *", min_value=1, step=1, value=1)
        commentaire = st.text_input(
            "Commentaire (optionnel)",
            placeholder="Ex : Vente comptoir, ticket n°1024",
        )
        submitted = st.form_submit_button("Enregistrer la sortie", type="primary")

    if not submitted:
        return

    sku = options[libelle]
    try:
        nouveau_stock = manager.remove_stock(sku, int(quantite), commentaire.strip())
        st.success(
            f"✅ Sortie enregistrée : -{quantite} unité(s) pour « {sku} ». "
            f"Nouveau stock : **{nouveau_stock}**."
        )
        st.rerun()
    except StockInsuffisantError as exc:
        # Message d'erreur explicite exigé par le cahier des charges :
        # le stock ne doit jamais devenir négatif.
        st.error(f"❌ Stock insuffisant : {exc}")
    except ProduitInexistantError as exc:
        st.error(f"❌ {exc}")
    except ValueError as exc:
        st.error(f"❌ {exc}")
    except Exception as exc:  # noqa: BLE001
        st.error(f"❌ Erreur lors de l'enregistrement de la sortie : {exc}")
