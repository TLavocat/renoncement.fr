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

## A. Formulaire REX (10 min)

Le formulaire existe déjà. À vérifier :

1. **Consentement** : dans l'introduction du formulaire (le texte sous le
   titre), les phrases suivantes doivent être visibles :
   > En soumettant ce formulaire, vous acceptez que votre récit soit publié
   > anonymement sous licence Creative Commons CC BY-NC 4.0 et réutilisé sous
   > forme anonyme par renoncement.fr (analyses, synthèses, projets futurs —
   > détails dans le règlement : https://renoncement.fr/reglement/), et vous
   > confirmez qu'il s'agit de votre propre vécu et que vous êtes
   > l'auteur·e du texte.
   >
   > Votre adresse e-mail (collectée via votre compte Google) sert uniquement
   > au tirage au sort annuel et à la modération. Elle n'est jamais publiée,
   > jamais transmise, et elle est purgée un mois après le tirage.
   >
   > Ne citez personne de manière reconnaissable dans votre récit (ni nom,
   > ni surnom, ni détail qui identifie quelqu'un).
2. **Collecte d'e-mail vérifiée** (anti-spam) : dans les paramètres du
   formulaire, garder « Collecter les adresses e-mail » en mode **Vérifiée** :
   soumettre exige une connexion à un compte Google, ce qui est la principale
   barrière anti-spam du site (le formulaire publie automatiquement — un champ
   e-mail libre n'offrirait aucune protection). Conséquences à assumer et
   affichées dans le règlement et les mentions légales : la soumission n'est
   pas anonyme vis-à-vis du mainteneur et de Google (seule la **publication**
   l'est), et l'adresse sert à deux choses — tirage au sort et modération.
   Le script de publication ne lit jamais cette colonne.
3. **Archiver le consentement** : après chaque modification du texte
   d'introduction, imprimer le formulaire en PDF (Ctrl+P) et le ranger avec sa
   date. C'est la preuve de ce à quoi les contributeurs ont consenti et quand.
4. **Supprimer la question photo/croquis** (« Souhaites-tu partager une photo… ») :
   les fichiers envoyés portent le nom du répondant et présentent un risque de
   sécurité. La colonne restante dans la feuille est ignorée par le script.
5. **Ne jamais renommer une question** après cette étape : les en-têtes de la
   feuille sont le texte exact des questions, et le script s'appuie dessus
   (en cas de renommage, la synchro échoue en listant les en-têtes attendus
   vs réels — rien n'est publié de travers, mais elle reste rouge jusqu'à
   correction de `REX_COLUMNS` dans `scripts/sync.py`).
   Éviter aussi les virgules dans les libellés de cases à cocher, sauf entre
   parenthèses.

### Formulaire v2 (2026-08-03)

Le formulaire a changé de structure : un champ libre `Raconte ton renoncement`
remplace les quatre questions de prose du v1 (plan de vol, détail des signaux,
déclencheur EXACT, bilan personnel), complété par `Le déclencheur final, en
une phrase` (accroche des cartes) et `Qu'en retires-tu pour tes prochains
vols ?` (facultatif). Le script détecte le format ligne par ligne : récit
libre rempli = gabarit v2, sinon gabarit v1 — les anciens REX restent rendus
à l'identique pour toujours. C'est pourquoi les colonnes des questions
supprimées ne doivent **jamais** être effacées de la feuille.

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
6. Dans `hugo.toml`, section `[params.rexReport]`, renseigner :
   - `formUrl` = l'URL `…/viewform` du formulaire de modération ;
   - `entryId` = `entry.NNNNNNNNN` (le numéro relevé au point 5).

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

1. Onglet **Actions → Lottery draw → Run workflow** :
   - une première fois avec **Dry run** coché (par défaut) : affiche la table
     des tickets (participants anonymisés par empreinte), sans tirer ;
   - une seconde fois avec **Dry run** décoché : le tirage réel.
2. Le résultat n'affiche **jamais d'adresse e-mail** (les journaux d'Actions
   d'un dépôt public sont lisibles par tous) : il donne un **numéro de ligne**
   de la feuille. Ouvrir la feuille de calcul à cette ligne (onglet des REX)
   pour lire l'adresse du gagnant.
3. Demander au gagnant sa licence FFVL de l'année en cours (ou licence
   fédérale équivalente) avant d'attribuer le lot (une journée de stage SIV,
   200 € max). La licence n'est pas conservée.
4. **Un mois après le tirage** : vider la colonne `Adresse e-mail` de la
   feuille (Règlement §3). Modifier des cellules ne change jamais les
   identifiants des REX — sauf la colonne `Horodateur`, à ne **jamais** éditer
   pour une ligne déjà publiée.

(Le script peut aussi tourner en local avec les deux variables d'environnement
exportées : `python scripts/draw.py --dry-run` — même sortie, même garantie.)

## Note de maintenance : la règle des 60 jours

Le contenu du site n'est jamais commité : la feuille Google est la source de
vérité et chaque exécution horaire régénère tout. Contrepartie : si le dépôt
ne reçoit aucun commit pendant 60 jours, GitHub prévient par e-mail puis met
en pause les exécutions planifiées. Le site reste en ligne (dernière version
publiée), seuls les nouveaux REX cessent d'apparaître. Pour reprendre : un
clic sur « Enable » dans l'onglet Actions, ou n'importe quel commit — la
première exécution rattrape tout, rien n'est perdu.
