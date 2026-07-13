"""
pages/alertes.py
=================
Page "Alertes" : liste complète des produits dont le stock est passé sous
leur seuil d'alerte (ZSET alertes:stock_bas), triés du plus urgent
(stock le plus bas) au moins urgent.
"""

from __future__ import annotations

import streamlit as st

from database import RedisManager


def render(manager: RedisManager) -> None:
    """
    Affiche la page Alertes.

    Args:
        manager: instance RedisManager connectée, injectée par app.py.
    """
    st.title("🚨 Alertes de rupture de stock")
    st.caption(
        "Produits dont le stock est passé sous leur seuil critique, "
        "du plus urgent au moins urgent."
    )

    try:
        alertes = manager.get_alerts()
    except Exception as exc:  # noqa: BLE001
        st.error(f"❌ Erreur lors du chargement des alertes : {exc}")
        return

    if not alertes:
        st.success("✅ Aucun produit en alerte. Tous les stocks sont au-dessus de leur seuil.")
        return

    st.metric("Nombre de produits en alerte", len(alertes))
    st.divider()

    for rang, alerte in enumerate(alertes, start=1):
        stock = alerte["stock"]
        seuil = alerte["seuil_alerte"]
        # Niveau de sévérité indicatif : rupture totale, très critique, ou simplement bas.
        if stock <= 0:
            niveau, couleur = "🔴 Rupture de stock", "red"
        elif seuil > 0 and stock <= seuil * 0.5:
            niveau, couleur = "🟠 Très critique", "orange"
        else:
            niveau, couleur = "🟡 Stock bas", "orange"

        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            col1.markdown(f"**#{rang} — {alerte['nom']}**  \n`{alerte['sku']}`")
            col2.metric("Stock actuel", stock)
            col3.metric("Seuil d'alerte", seuil)
            col4.markdown(f":{couleur}[**{niveau}**]")

    st.divider()
    st.caption(
        "💡 Rendez-vous sur la page **🔁 Mouvements** pour enregistrer une "
        "entrée de stock et lever ces alertes."
    )
