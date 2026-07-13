"""
app.py
======
Point d'entrée de l'application Streamlit GestiStock.

Ce fichier gère uniquement :
    - la configuration globale de la page,
    - l'initialisation (mise en cache) de la connexion Redis,
    - la sidebar de navigation,
    - le routage vers les différentes pages de l'application.

Aucun appel Redis direct n'est effectué ici : toute la logique de données
est déléguée à database.py (classe RedisManager), conformément au cahier
des charges du module NoSQL.
"""

from __future__ import annotations

import streamlit as st

from database import RedisManager

# --------------------------------------------------------------------------
# Configuration générale de la page
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="GestiStock — Gestion de stock en temps réel",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------------------------------
# Connexion Redis mise en cache (une seule connexion pour toute la session)
# --------------------------------------------------------------------------
@st.cache_resource(show_spinner="Connexion à la base Upstash Redis...")
def get_redis_manager() -> RedisManager:
    """
    Instancie et connecte le RedisManager une seule fois par session
    serveur, puis le réutilise pour toutes les pages de l'application.

    Returns:
        Une instance de RedisManager connectée à Upstash.
    """
    manager = RedisManager()
    manager.connect()
    return manager


def init_app() -> RedisManager | None:
    """
    Tente d'établir la connexion Redis et affiche un message d'erreur
    explicite dans l'interface en cas d'échec (REDIS_URL manquant,
    identifiants invalides, base injoignable, etc.).

    Returns:
        Le RedisManager connecté, ou None si la connexion a échoué.
    """
    try:
        return get_redis_manager()
    except Exception as exc:  # noqa: BLE001 - on veut capturer toute erreur réseau/config
        st.error(
            "❌ Impossible de se connecter à la base Redis Upstash.\n\n"
            f"Détail : {exc}\n\n"
            "Vérifiez que la variable REDIS_URL est correctement définie "
            "dans votre fichier .env (en local) ou dans les Secrets "
            "Streamlit Cloud (en production)."
        )
        return None


# --------------------------------------------------------------------------
# Sidebar de navigation
# --------------------------------------------------------------------------
def render_sidebar(manager: RedisManager) -> str:
    """
    Affiche la sidebar de navigation et un mini résumé des alertes en cours.

    Args:
        manager: instance RedisManager connectée, utilisée pour afficher
            un compteur d'alertes rapide dans la sidebar.

    Returns:
        Le libellé de la page sélectionnée par l'utilisateur.
    """
    with st.sidebar:
        st.markdown("## 📦 GestiStock")
        st.caption("Gestion de stock en temps réel — Redis / Upstash")
        st.divider()

        page = st.radio(
            "Navigation",
            options=[
                "🏠 Dashboard",
                "🗂️ Produits",
                "🔁 Mouvements",
                "📜 Historique",
                "🚨 Alertes",
            ],
            label_visibility="collapsed",
        )

        st.divider()

        # Petit résumé rapide des alertes, visible depuis n'importe quelle page.
        try:
            nb_alertes = len(manager.get_alerts())
            if nb_alertes > 0:
                st.warning(f"🚨 {nb_alertes} produit(s) en alerte de stock")
            else:
                st.success("✅ Aucune alerte de stock")
        except Exception:  # noqa: BLE001 - ne doit jamais bloquer la sidebar
            pass

        st.divider()
        st.caption("GROUPE 3 — Module NoSQL (Redis)")
        st.caption("ECES — 3e année Data Science — 2025/2026")

    return page


# --------------------------------------------------------------------------
# Routage vers les pages
# --------------------------------------------------------------------------
def route_page(page: str, manager: RedisManager) -> None:
    """
    Appelle la fonction render() de la page sélectionnée en lui passant
    le RedisManager connecté.

    Args:
        page: libellé de la page choisie dans la sidebar.
        manager: instance RedisManager connectée.
    """
    # Les imports sont faits ici (et non en tête de fichier) pour que
    # chaque page ne soit chargée que lorsqu'elle est réellement affichée.
    if page == "🏠 Dashboard":
        from pages import dashboard
        dashboard.render(manager)
    elif page == "🗂️ Produits":
        from pages import produits
        produits.render(manager)
    elif page == "🔁 Mouvements":
        from pages import mouvements
        mouvements.render(manager)
    elif page == "📜 Historique":
        from pages import historique
        historique.render(manager)
    elif page == "🚨 Alertes":
        from pages import alertes
        alertes.render(manager)


# --------------------------------------------------------------------------
# Point d'entrée
# --------------------------------------------------------------------------
def main() -> None:
    """Fonction principale : initialise la connexion et lance le routage."""
    manager = init_app()
    if manager is None:
        st.stop()

    page = render_sidebar(manager)
    route_page(page, manager)


if __name__ == "__main__":
    main()
