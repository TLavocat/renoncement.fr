# SETUP — activation du site, étape par étape

Le dépôt contient tout le code ; le site s'active progressivement à mesure que
les étapes ci-dessous sont complétées. Chaque étape est indépendante : tant
qu'elle n'est pas faite, la fonctionnalité correspondante reste simplement
inactive (rien ne casse).

Résumé des étapes :

| Étape | Effet une fois faite |
|---|---|
| A. Formulaire REX | Consentement affiché, champ photo supprimé |
| B. Formulaire de modération | Signalement + quarantaine possibles |
| C. Compte de service Google | Le script peut lire la feuille privée |
| D. Secrets GitHub | La synchronisation horaire démarre |
| E. GitHub Pages + domaine | Le site est en ligne sur renoncement.fr |
| F. DNS | Le domaine pointe vers GitHub |
| G. Discussions + giscus | Les commentaires apparaissent sous les REX |
| H. Tirage annuel | Rituel de fin de saison |

---

## A. Formulaire REX (5 min)

Le formulaire existe déjà. Trois vérifications :

1. **Consentement** : dans l'introduction du formulaire (le texte sous le
   titre), la phrase suivante doit être visible :
   > En soumettant ce formulaire, vous acceptez la publication anonyme de
   > votre récit, et vous confirmez qu'il s'agit de votre propre vécu.
2. **Supprimer la question photo/croquis** (« Souhaites-tu partager une photo… ») :
   les fichiers envoyés portent le nom du répondant et présentent un risque de
   sécurité. La colonne restante dans la feuille est ignorée par le script.
3. **Ne jamais renommer une question** après cette étape : les en-têtes de la
   feuille sont le texte exact des questions, et le script s'appuie dessus
   (en cas de renommage, la synchro échoue en listant les en-têtes attendus
   vs réels — rien n'est publié de travers, mais elle reste rouge jusqu'à
   correction de `REX_COLUMNS` dans `scripts/sync.py`).
   Éviter aussi les virgules dans les libellés de cases à cocher, sauf entre
   parenthèses.

## B. Formulaire de modération (10 min)

1. Créer un formulaire Google nommé par exemple « Signaler un REX », avec **une
   seule question** de type réponse courte, intitulée exactement : `rex_id`.
2. Le lier à la **même feuille de calcul** que le formulaire REX :
   onglet **Réponses → icône Sheets verte → Sélectionner une feuille de calcul
   existante** → choisir la feuille des REX. Un deuxième onglet apparaît.
3. Vérifier les noms exacts des deux onglets (en bas de la feuille). S'ils
   diffèrent de `Réponses au formulaire 1` / `Réponses au formulaire 2`,
   reporter les bons noms dans `REX_WORKSHEET` / `MOD_WORKSHEET`
   (`scripts/sync.py`).
4. Dans l'onglet de modération, ajouter l'en-tête `Validé` dans la première
   colonne vide, puis sélectionner la colonne → **Insertion → Case à cocher**.
   Un signalement ne retire un REX que lorsque cette case est cochée par le
   mainteneur ; pour restaurer un REX, il suffit de la décocher.
5. Récupérer l'identifiant de pré-remplissage : dans l'éditeur du formulaire,
   **⋮ → Obtenir le lien pré-rempli** → taper `test` dans le champ →
   **Obtenir le lien** → copier. L'URL contient `entry.NNNNNNNNN=test`.
6. Dans `scripts/sync.py`, renseigner :
   - `REPORT_FORM_URL` = l'URL `…/viewform` du formulaire de modération ;
   - `REPORT_ENTRY_ID` = `entry.NNNNNNNNN` (le numéro relevé au point 5).

   Commiter. Chaque REX affichera alors un lien « Signaler ce REX » pré-rempli.

## C. Compte de service Google (15 min)

C'est le « jeton » qui permet au script de lire la feuille **privée** (jamais
publiée sur le web — elle contient les adresses e-mail).

1. Aller sur <https://console.cloud.google.com> (connecté avec le compte Google
   propriétaire de la feuille).
2. Sélecteur de projet (barre du haut) → **Nouveau projet** → nom :
   `renoncement-fr` → **Créer**, puis le sélectionner.
3. **☰ Menu → API et services → Bibliothèque** → chercher « Google Sheets API »
   → **Activer**. (Seulement celle-ci ; l'API Drive n'est pas nécessaire.)
4. **☰ Menu → IAM et administration → Comptes de service** →
   **Créer un compte de service** → nom : `renoncement-sync` → **Créer et
   continuer** → **ignorer les deux écrans facultatifs** (aucun rôle à donner)
   → **OK**.
5. Cliquer sur le compte créé → onglet **Clés** → **Ajouter une clé → Créer une
   clé → JSON → Créer**. Un fichier `.json` se télécharge : c'est le mot de
   passe du compte — ne jamais le commiter ni le partager.
6. Copier l'adresse e-mail du compte (forme
   `renoncement-sync@renoncement-fr.iam.gserviceaccount.com`) → ouvrir la
   feuille de calcul → **Partager** → coller cette adresse → rôle **Lecteur**
   → **Envoyer** (ignorer l'avertissement « impossible d'envoyer une
   notification »).
7. Noter l'**ID de la feuille** : la longue chaîne dans l'URL entre `/d/` et
   `/edit` (`docs.google.com/spreadsheets/d/` **`1AbC…xYz`** `/edit`).

## D. Secrets GitHub (5 min)

1. Page du dépôt → **Settings → Secrets and variables → Actions →
   New repository secret**.
2. Secret 1 : nom `GOOGLE_SERVICE_ACCOUNT_JSON`, valeur = **tout le contenu**
   du fichier `.json` téléchargé en C5 (l'ouvrir dans un éditeur de texte,
   tout sélectionner, coller).
3. Secret 2 : nom `GOOGLE_SHEET_ID`, valeur = l'ID relevé en C7.
4. **Aucun jeton GitHub à créer** : le workflow utilise le `GITHUB_TOKEN`
   automatique fourni par Actions.
5. Supprimer ensuite le fichier `.json` de l'ordinateur (ou le ranger dans un
   gestionnaire de mots de passe) — il servira à nouveau pour le tirage (H).

Test : onglet **Actions → Sync and deploy → Run workflow**. Soumettre un REX de
test via le formulaire, relancer : la page apparaît sur le site.

## E. GitHub Pages + domaine

1. **Settings → Pages** : Source = **GitHub Actions** ; Custom domain =
   `renoncement.fr` → **Save** ; cocher **Enforce HTTPS** dès que le certificat
   est émis (jusqu'à ~1 h après la mise en place du DNS).
2. Anti-détournement : profil personnel → **Settings → Pages → Add a domain** →
   vérifier `renoncement.fr` via l'enregistrement TXT indiqué.

## F. DNS (chez le registrar)

| Nom | Type | Valeur |
|---|---|---|
| `renoncement.fr` | A | `185.199.108.153` |
| `renoncement.fr` | A | `185.199.109.153` |
| `renoncement.fr` | A | `185.199.110.153` |
| `renoncement.fr` | A | `185.199.111.153` |
| `www` | CNAME | `tlavocat.github.io` |

(Facultatif, IPv6 : AAAA `2606:50c0:8000::153` à `2606:50c0:8003::153`.)

Vérifier : `dig renoncement.fr +short` doit lister les quatre adresses.

## G. Discussions + giscus (commentaires)

1. Dépôt → **Settings → General → Features** → cocher **Discussions**.
2. Dans l'onglet Discussions, créer une catégorie **Commentaires** de type
   **Announcement** (ainsi seul giscus peut créer des fils).
3. Installer l'application giscus : <https://github.com/apps/giscus> →
   **Install** → uniquement ce dépôt.
4. Sur <https://giscus.app> : renseigner `TLavocat/renoncement.fr`, choisir la
   catégorie Commentaires → la page affiche `data-repo-id` et
   `data-category-id`.
5. Reporter ces deux valeurs dans `hugo.toml` (`[params.giscus]` → `repoID` et
   `categoryID`) et commiter. Les commentaires apparaissent sous chaque REX.

Note : un REX sans commentaire affiche une zone vide — le fil de discussion
n'est créé qu'au premier commentaire, c'est normal.

## H. Tirage annuel (fin de saison)

1. Sur l'ordinateur du mainteneur :

   ```bash
   export GOOGLE_SHEET_ID="…"                                # ID relevé en C7
   export GOOGLE_SERVICE_ACCOUNT_JSON="$(cat service-account.json)"
   pip install -r scripts/requirements.txt
   python scripts/draw.py --dry-run   # table des tickets, sans tirage
   python scripts/draw.py             # tirage réel
   ```

   Ce script ne doit **jamais** tourner dans GitHub Actions : il lit la colonne
   e-mail, et les journaux d'Actions d'un dépôt public sont lisibles par tous.
2. Vérifier l'activité de vol du gagnant (trace CFD) avant d'attribuer le lot
   (une journée de stage SIV, 200 € max).
3. **Un mois après le tirage** : vider la colonne `Adresse e-mail` de la
   feuille (Règlement §3). Modifier des cellules ne change jamais les
   identifiants des REX — sauf la colonne `Horodateur`, à ne **jamais** éditer
   pour une ligne déjà publiée.
