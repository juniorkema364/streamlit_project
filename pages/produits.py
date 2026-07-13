"""
pages/produits.py
==================
Page "Produits" : référentiel produits (HASH produit:<sku>).

Permet :
    - d'ajouter un nouveau produit (formulaire avec stock initial)
    - de modifier un produit existant
    - de supprimer un produit (avec toutes ses clés associées)
    - de rechercher un produit par SKU ou par nom
    - d'afficher tous les produits avec leur stock actuel
"""

from __future__ import annotations

import streamlit as st

from database import (
    ProduitDejaExistantError,
    ProduitInexistantError,
    RedisManager,
)

CATEGORIES = [
    "Alimentaire",
    "Boisson",
    "Hygiène",
    "Électronique",
    "Textile",
    "Papeterie",
    "Autre",
]


def render(manager: RedisManager) -> None:
    """
    Affiche la page Produits.

    Args:
        manager: instance RedisManager connectée, injectée par app.py.
    """
    st.title("🗂️ Gestion des produits")
    st.caption("Référentiel produits — ajout, modification, suppression, recherche")

    tab_liste, tab_ajout, tab_modif, tab_suppr = st.tabs(
        ["📋 Liste & recherche", "➕ Ajouter", "✏️ Modifier", "🗑️ Supprimer"]
    )

    with tab_liste:
        _render_liste_recherche(manager)

    with tab_ajout:
        _render_formulaire_ajout(manager)

    with tab_modif:
        _render_formulaire_modification(manager)

    with tab_suppr:
        _render_formulaire_suppression(manager)


# --------------------------------------------------------------------------
# Onglet : Liste & recherche
# --------------------------------------------------------------------------
def _render_liste_recherche(manager: RedisManager) -> None:
    try:
        produits = manager.get_all_products()
    except Exception as exc:  # noqa: BLE001
        st.error(f"❌ Erreur lors du chargement des produits : {exc}")
        return

    if not produits:
        st.info("Aucun produit référencé pour le moment. Utilisez l'onglet **➕ Ajouter**.")
        return

    recherche = st.text_input(
        "🔍 Rechercher un produit (par SKU ou nom)",
        placeholder="Ex : SKU-001 ou Riz",
    )

    if recherche:
        terme = recherche.strip().lower()
        produits = [
            p for p in produits
            if terme in p["sku"].lower() or terme in p["nom"].lower()
        ]
        if not produits:
            st.warning(f"Aucun produit ne correspond à « {recherche} ».")
            return

    st.dataframe(
        [
            {
                "SKU": p["sku"],
                "Nom": p["nom"],
                "Catégorie": p["categorie"],
                "Stock actuel": p["stock"],
                "Seuil d'alerte": p["seuil_alerte"],
                "Prix unitaire": f"{p['prix_unitaire']:.2f}",
                "Fournisseur": p["fournisseur"],
                "État": "🚨 Alerte" if p["stock"] < p["seuil_alerte"] else "✅ OK",
            }
            for p in produits
        ],
        use_container_width=True,
        hide_index=True,
    )


# --------------------------------------------------------------------------
# Onglet : Ajouter
# --------------------------------------------------------------------------
def _render_formulaire_ajout(manager: RedisManager) -> None:
    st.subheader("➕ Ajouter un nouveau produit")

    with st.form("form_ajout_produit", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            sku = st.text_input("SKU (identifiant unique) *", placeholder="Ex : SKU-001")
            nom = st.text_input("Nom du produit *", placeholder="Ex : Riz parfumé 5kg")
            categorie = st.selectbox("Catégorie *", CATEGORIES)
        with col2:
            prix_unitaire = st.number_input(
                "Prix unitaire *", min_value=0.0, step=100.0, format="%.2f"
            )
            seuil_alerte = st.number_input(
                "Seuil d'alerte *", min_value=0, step=1, value=5
            )
            fournisseur = st.text_input("Fournisseur *", placeholder="Ex : Grossiste Poto-Poto")

        stock_initial = st.number_input(
            "Stock initial", min_value=0, step=1, value=0,
            help="Quantité en stock au moment de la création du produit.",
        )

        submitted = st.form_submit_button("Créer le produit", type="primary")

    if not submitted:
        return

    # -- Validation du formulaire --
    erreurs = []
    if not sku.strip():
        erreurs.append("Le SKU est obligatoire.")
    if not nom.strip():
        erreurs.append("Le nom du produit est obligatoire.")
    if not fournisseur.strip():
        erreurs.append("Le fournisseur est obligatoire.")
    if prix_unitaire <= 0:
        erreurs.append("Le prix unitaire doit être strictement positif.")

    if erreurs:
        for erreur in erreurs:
            st.error(f"❌ {erreur}")
        return

    try:
        manager.add_product(
            sku=sku.strip(),
            nom=nom.strip(),
            categorie=categorie,
            prix_unitaire=prix_unitaire,
            seuil_alerte=int(seuil_alerte),
            fournisseur=fournisseur.strip(),
            stock_initial=int(stock_initial),
        )
        st.success(f"✅ Produit « {nom} » ({sku}) créé avec succès.")
        st.rerun()
    except ProduitDejaExistantError as exc:
        st.error(f"❌ {exc}")
    except Exception as exc:  # noqa: BLE001
        st.error(f"❌ Erreur lors de la création du produit : {exc}")


# --------------------------------------------------------------------------
# Onglet : Modifier
# --------------------------------------------------------------------------
def _render_formulaire_modification(manager: RedisManager) -> None:
    st.subheader("✏️ Modifier un produit existant")

    try:
        produits = manager.get_all_products()
    except Exception as exc:  # noqa: BLE001
        st.error(f"❌ Erreur lors du chargement des produits : {exc}")
        return

    if not produits:
        st.info("Aucun produit à modifier pour le moment.")
        return

    skus = [p["sku"] for p in produits]
    sku_selectionne = st.selectbox("Sélectionner un produit à modifier", skus)
    produit = next(p for p in produits if p["sku"] == sku_selectionne)

    with st.form("form_modif_produit"):
        col1, col2 = st.columns(2)
        with col1:
            nom = st.text_input("Nom du produit", value=produit["nom"])
            categorie = st.selectbox(
                "Catégorie",
                CATEGORIES,
                index=CATEGORIES.index(produit["categorie"])
                if produit["categorie"] in CATEGORIES else len(CATEGORIES) - 1,
            )
        with col2:
            prix_unitaire = st.number_input(
                "Prix unitaire", min_value=0.0, step=100.0,
                value=float(produit["prix_unitaire"]), format="%.2f",
            )
            seuil_alerte = st.number_input(
                "Seuil d'alerte", min_value=0, step=1,
                value=int(produit["seuil_alerte"]),
            )
        fournisseur = st.text_input("Fournisseur", value=produit["fournisseur"])

        submitted = st.form_submit_button("Enregistrer les modifications", type="primary")

    if not submitted:
        return

    if not nom.strip() or not fournisseur.strip():
        st.error("❌ Le nom et le fournisseur ne peuvent pas être vides.")
        return
    if prix_unitaire <= 0:
        st.error("❌ Le prix unitaire doit être strictement positif.")
        return

    try:
        manager.update_product(
            sku=sku_selectionne,
            nom=nom.strip(),
            categorie=categorie,
            prix_unitaire=prix_unitaire,
            seuil_alerte=int(seuil_alerte),
            fournisseur=fournisseur.strip(),
        )
        st.success(f"✅ Produit « {sku_selectionne} » mis à jour avec succès.")
        st.rerun()
    except ProduitInexistantError as exc:
        st.error(f"❌ {exc}")
    except Exception as exc:  # noqa: BLE001
        st.error(f"❌ Erreur lors de la modification du produit : {exc}")


# --------------------------------------------------------------------------
# Onglet : Supprimer
# --------------------------------------------------------------------------
def _render_formulaire_suppression(manager: RedisManager) -> None:
    st.subheader("🗑️ Supprimer un produit")
    st.warning(
        "⚠️ Cette action est irréversible : elle supprime le produit, "
        "son stock et tout son historique de mouvements."
    )

    try:
        produits = manager.get_all_products()
    except Exception as exc:  # noqa: BLE001
        st.error(f"❌ Erreur lors du chargement des produits : {exc}")
        return

    if not produits:
        st.info("Aucun produit à supprimer pour le moment.")
        return

    skus = [p["sku"] for p in produits]
    sku_selectionne = st.selectbox(
        "Sélectionner un produit à supprimer", skus, key="select_suppression"
    )
    produit = next(p for p in produits if p["sku"] == sku_selectionne)

    st.write(
        f"Vous êtes sur le point de supprimer **{produit['nom']}** "
        f"(`{sku_selectionne}`) — stock actuel : {produit['stock']}."
    )

    confirmation = st.checkbox("Je confirme vouloir supprimer ce produit définitivement.")

    if st.button("Supprimer le produit", type="primary", disabled=not confirmation):
        try:
            manager.delete_product(sku_selectionne)
            st.success(f"✅ Produit « {sku_selectionne} » supprimé avec succès.")
            st.rerun()
        except ProduitInexistantError as exc:
            st.error(f"❌ {exc}")
        except Exception as exc:  # noqa: BLE001
            st.error(f"❌ Erreur lors de la suppression du produit : {exc}")
