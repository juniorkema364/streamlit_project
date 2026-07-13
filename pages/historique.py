"""
pages/historique.py
====================
Page "Historique" : consultation des mouvements récents d'un produit
sélectionné (LIST historique:<sku>, limitée à 50 éléments via LTRIM côté
database.py, dont les 20 plus récents sont affichés ici).
"""

from __future__ import annotations

import streamlit as st

from database import HISTORIQUE_DISPLAY_LEN, RedisManager
from utils.helpers import format_timestamp


def render(manager: RedisManager) -> None:
    """
    Affiche la page Historique.

    Args:
        manager: instance RedisManager connectée, injectée par app.py.
    """
    st.title("📜 Historique des mouvements")
    st.caption(
        f"Consultez les {HISTORIQUE_DISPLAY_LEN} derniers mouvements "
        "d'un produit sélectionné"
    )

    try:
        produits = manager.get_all_products()
    except Exception as exc:  # noqa: BLE001
        st.error(f"❌ Erreur lors du chargement des produits : {exc}")
        return

    if not produits:
        st.info("Aucun produit référencé pour le moment.")
        return

    options = {f"{p['nom']} ({p['sku']})": p["sku"] for p in produits}
    libelle = st.selectbox("Sélectionner un produit", list(options.keys()))
    sku = options[libelle]

    produit = next(p for p in produits if p["sku"] == sku)

    col1, col2, col3 = st.columns(3)
    col1.metric("Stock actuel", produit["stock"])
    col2.metric("Seuil d'alerte", produit["seuil_alerte"])
    col3.metric(
        "État",
        "🚨 Alerte" if produit["stock"] < produit["seuil_alerte"] else "✅ OK",
    )

    st.divider()

    try:
        mouvements = manager.get_history(sku, limit=HISTORIQUE_DISPLAY_LEN)
    except Exception as exc:  # noqa: BLE001
        st.error(f"❌ Erreur lors du chargement de l'historique : {exc}")
        return

    if not mouvements:
        st.info(f"Aucun mouvement enregistré pour « {sku} » pour le moment.")
        return

    st.subheader(f"Derniers mouvements ({len(mouvements)})")

    for mvt in mouvements:
        timestamp = format_timestamp(mvt.get("timestamp", ""))
        type_mvt = mvt.get("type", "inconnu")
        quantite = mvt.get("quantite", 0)
        commentaire = mvt.get("commentaire", "")

        if type_mvt == "entree":
            icone, signe, couleur = "⬆️", "+", "green"
        else:
            icone, signe, couleur = "⬇️", "-", "red"

        texte = f"{icone} :{couleur}[**{signe}{quantite}**] — {timestamp}"
        if commentaire:
            texte += f" — _{commentaire}_"
        st.markdown(texte)

    # Vue tabulaire alternative, pratique pour un export/copier-coller.
    with st.expander("📊 Voir sous forme de tableau"):
        st.dataframe(
            [
                {
                    "Type": "Entrée" if m.get("type") == "entree" else "Sortie",
                    "Quantité": m.get("quantite", 0),
                    "Date": format_timestamp(m.get("timestamp", "")),
                    "Commentaire": m.get("commentaire", ""),
                }
                for m in mouvements
            ],
            use_container_width=True,
            hide_index=True,
        )
