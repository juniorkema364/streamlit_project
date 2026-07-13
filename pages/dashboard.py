"""
pages/dashboard.py
===================
Page "Dashboard" : vue d'ensemble en un coup d'œil de l'état du stock.

Affiche :
    - les métriques KPI globales (nb produits, nb alertes, entrées/sorties 24h)
    - le Top 3 des produits avec le stock le plus faible
    - un aperçu rapide des alertes critiques
"""

from __future__ import annotations

import streamlit as st

from database import RedisManager
from utils.helpers import format_currency, stock_badge


def render(manager: RedisManager) -> None:
    """
    Affiche la page Dashboard.

    Args:
        manager: instance RedisManager connectée, injectée par app.py.
    """
    st.title("🏠 Dashboard")
    st.caption("Vue d'ensemble en temps réel de votre stock")

    try:
        stats = manager.get_statistics()
    except Exception as exc:  # noqa: BLE001
        st.error(f"❌ Erreur lors du chargement des statistiques : {exc}")
        return

    # ------------------------------------------------------------------
    # Métriques KPI
    # ------------------------------------------------------------------
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📦 Produits référencés", stats["nb_produits_total"])
    col2.metric(
        "🚨 Produits en alerte",
        stats["nb_produits_alerte"],
        delta=None if stats["nb_produits_alerte"] == 0 else "à surveiller",
        delta_color="inverse",
    )
    col3.metric("⬆️ Entrées (24h)", stats["entrees_24h"])
    col4.metric("⬇️ Sorties (24h)", stats["sorties_24h"])

    st.divider()

    # ------------------------------------------------------------------
    # Top 3 des stocks les plus faibles + aperçu des alertes
    # ------------------------------------------------------------------
    left, right = st.columns([1, 1])

    with left:
        st.subheader("📉 Top 3 — Stocks les plus faibles")
        top3 = stats["top3_stocks_faibles"]
        if not top3:
            st.info("Aucun produit référencé pour le moment.")
        else:
            for rang, produit in enumerate(top3, start=1):
                medaille = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rang, "•")
                st.write(
                    f"{medaille} **{produit['nom']}** "
                    f"(`{produit['sku']}`) — stock : **{produit['stock']}**"
                )

    with right:
        st.subheader("🚨 Alertes critiques")
        try:
            alertes = manager.get_alerts()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Erreur lors du chargement des alertes : {exc}")
            alertes = []

        if not alertes:
            st.success("✅ Aucun produit en dessous de son seuil d'alerte.")
        else:
            for alerte in alertes[:5]:
                st.error(
                    f"**{alerte['nom']}** (`{alerte['sku']}`) — "
                    f"stock : {alerte['stock']} / seuil : {alerte['seuil_alerte']}"
                )
            if len(alertes) > 5:
                st.caption(
                    f"... et {len(alertes) - 5} autre(s) produit(s) en alerte. "
                    "Voir la page **🚨 Alertes** pour la liste complète."
                )

    st.divider()

    # ------------------------------------------------------------------
    # Tableau complet des produits
    # ------------------------------------------------------------------
    st.subheader("📋 Vue d'ensemble des produits")
    try:
        produits = manager.get_all_products()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Erreur lors du chargement des produits : {exc}")
        return

    if not produits:
        st.info("Aucun produit référencé. Rendez-vous sur la page **🗂️ Produits** pour en ajouter.")
        return

    st.dataframe(
        [
            {
                "SKU": p["sku"],
                "Nom": p["nom"],
                "Catégorie": p["categorie"],
                "Stock actuel": p["stock"],
                "Seuil d'alerte": p["seuil_alerte"],
                "Prix unitaire": format_currency(p["prix_unitaire"]),
                "Fournisseur": p["fournisseur"],
                "État": stock_badge(p["stock"], p["seuil_alerte"]),
            }
            for p in produits
        ],
        use_container_width=True,
        hide_index=True,
    )
