# 📦 GestiStock — Tableau de bord de gestion de stock en temps réel

Application web de gestion de stock centralisée, développée avec **Streamlit** et
**Redis (Upstash)**, dans le cadre de l'examen du 4ᵉ semestre — module **Base de
données NoSQL** (Key-Value Store) — ECES, 3ᵉ année Data Science, 2025/2026.

**Groupe 3** — MOUANGA Gloire, MATSIONA Aude Olvine, KEMA Didier Placide

---

## 📖 Description du projet

Une petite chaîne de magasins a besoin d'un système léger et rapide pour :

- gérer un référentiel de produits,
- enregistrer les entrées (réceptions fournisseur) et sorties (ventes) de stock,
- consulter un historique récent des mouvements,
- être alertée automatiquement lorsqu'un produit passe sous son seuil critique,
- suivre des statistiques globales en temps réel.

Redis a été choisi pour exploiter nativement ses structures de données les plus
adaptées à ce cas d'usage : compteurs atomiques (`INCRBY`/`DECRBY`) pour le stock,
`Sorted Set` pour les alertes triées par urgence, `List` pour l'historique, et
compteurs à `TTL` pour les statistiques glissantes sur 24h.

---

## 🏗️ Architecture

```
mon-projet-nosql/
│
├── app.py                    # Point d'entrée Streamlit (connexion, sidebar, routage)
├── database.py                 # Toute la logique Redis (classe RedisManager)
├── requirements.txt            # Dépendances Python
├── .env.example                 # Modèle des variables d'environnement
├── .gitignore                    # Fichiers/dossiers exclus de Git
│
├── pages/
│   ├── dashboard.py              # KPI, alertes, top 3 stocks faibles
│   ├── produits.py               # CRUD produits
│   ├── mouvements.py             # Entrées/sorties de stock
│   ├── historique.py             # 20 derniers mouvements par produit
│   └── alertes.py                # Liste complète des produits en rupture
│
└── utils/
    └── helpers.py                # Formatage, validation, badges réutilisables
```

**Principe de séparation stricte** : toutes les commandes Redis sont encapsulées
dans `database.py` (classe `RedisManager`). Aucune commande Redis n'est exécutée
directement depuis `app.py` ou les pages.

### Modélisation des données Redis

| Clé | Type | Rôle |
|---|---|---|
| `produit:<sku>` | HASH | Fiche produit (nom, catégorie, prix, seuil, fournisseur) |
| `stock:<sku>` | STRING | Stock actuel, manipulé via `INCRBY`/`DECRBY` |
| `historique:<sku>` | LIST | 50 derniers mouvements (JSON), tronquée via `LTRIM` |
| `alertes:stock_bas` | ZSET (Sorted Set) | SKU en alerte, score = stock actuel |
| `stats:entrees:24h` | STRING + TTL | Compteur d'entrées glissant sur 24h |
| `stats:sorties:24h` | STRING + TTL | Compteur de sorties glissant sur 24h |

---

## ⚙️ Installation (en local)

### Prérequis
- Python 3.10 ou supérieur
- Un compte [Upstash](https://upstash.com) (gratuit, sans carte bancaire)

### Étapes

1. **Cloner le dépôt**
   ```bash
   git clone https://github.com/<votre-utilisateur>/<votre-depot>.git
   cd mon-projet-nosql
   ```

2. **Créer et activer un environnement virtuel**
   ```bash
   python3 -m venv venv
   source venv/bin/activate      # macOS / Linux
   venv\Scripts\activate         # Windows
   ```

3. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurer les variables d'environnement**
   ```bash
   cp .env.example .env
   ```
   Puis éditer `.env` et renseigner votre `REDIS_URL` (voir section suivante).

5. **Lancer l'application**
   ```bash
   streamlit run app.py
   ```
   L'application s'ouvre automatiquement sur `http://localhost:8501`.

---

## ☁️ Configuration Upstash (Redis cloud gratuit)

1. Créer un compte sur [console.upstash.com](https://console.upstash.com).
2. Cliquer sur **Create Database**, choisir une région proche, type **Regional**.
3. Une fois la base créée, ouvrir l'onglet **Redis Connect**.
4. Copier l'URL au format **TLS** (commence par `rediss://`) :
   ```
   rediss://default:gQAAAAAAAn3XAAIgcDIyMzg1ZTg5NzA1MWI0ZTAzODM5ZDRhMGRkNzY0NDZiNA@mighty-penguin-163287.upstash.io:6379
   ```
5. Coller cette URL dans votre fichier `.env` :
   ```
    REDIS_URL=rediss://default:gQAAAAAAAn3XAAIgcDIyMzg1ZTg5NzA1MWI0ZTAzODM5ZDRhMGRkNzY0NDZiNA@mighty-penguin-163287.upstash.io:6379
   ```

Aucune carte bancaire n'est requise pour le plan gratuit (10 000 commandes/jour,
largement suffisant pour ce projet académique).

---

## 🚀 Déploiement sur Streamlit Community Cloud

1. Pousser le projet sur un **dépôt GitHub public** (obligatoire selon le barème —
   un dépôt privé vaut 0 point sur la partie GitHub).
2. Se rendre sur [share.streamlit.io](https://streamlit.io/cloud) et se connecter
   avec son compte GitHub.
3. Cliquer sur **New app**, sélectionner le dépôt et le fichier `app.py`.
4. Dans **Advanced settings > Secrets**, ajouter :
   ```toml
    REDIS_URL=rediss://default:gQAAAAAAAn3XAAIgcDIyMzg1ZTg5NzA1MWI0ZTAzODM5ZDRhMGRkNzY0NDZiNA@mighty-penguin-163287.upstash.io:6379"
   ```
   (Ne jamais commit ce secret dans le dépôt — c'est le rôle du `.gitignore`.)
5. Cliquer sur **Deploy**. L'application sera accessible via une URL du type
   `https://didier-gloire-aude.streamlit.app/`.

---

## 🔗 Liens du projet

- **Dépôt GitHub** : `https://github.com/juniorkema364/streamlit_project`
- **Application déployée** : `https://didier-gloire-aude.streamlit.app/`
 

---
 

Pour le rapport technique et ce README, prévoir des captures d'écran de :

- [ ] Page Dashboard avec métriques KPI
- [ ] Formulaire d'ajout de produit
- [ ] Liste des produits avec recherche
- [ ] Formulaire d'entrée / sortie de stock
- [ ] Message d'erreur "stock insuffisant"
- [ ] Page Historique d'un produit
- [ ] Page Alertes avec produits critiques
- [ ] Console Upstash montrant les clés créées (`produit:*`, `stock:*`, etc.)

---

## 🧩 Fonctionnalités implémentées

- ✅ Gestion complète des produits (ajouter, modifier, supprimer, rechercher, lister)
- ✅ Entrées/sorties de stock atomiques (`INCRBY`/`DECRBY`), stock jamais négatif
- ✅ Historique des mouvements (50 max en base, 20 affichés)
- ✅ Alertes automatiques triées par urgence (Sorted Set)
- ✅ Statistiques globales avec compteurs 24h (TTL)
- ✅ Interface Streamlit avec sidebar, KPI, tableaux interactifs, messages de succès/erreur

## 🛠️ Stack technique

Python 3.10+ · Streamlit · Redis (Upstash) · python-dotenv · redis-py

## 👥 Auteurs

Groupe 3 — Module NoSQL (Key-Value Store / Redis) — ECES, 2025/2026
Proposé par M. OBANDA Jefferson
