# toktool

Vous donnez une **URL YouTube** et un **timecode**, toktool crée un **clip de
60 s maximum** (format vertical 9:16 prêt pour TikTok) et peut le **publier
automatiquement sur TikTok** via l'API officielle.

```
URL YouTube + timecode ──> yt-dlp ──> ffmpeg (découpe + 9:16) ──> TikTok
```

Deux façons de l'utiliser :

- **📱 Depuis le téléphone, sans PC** — via un bouton dans GitHub Actions
  (voir [« Utilisation depuis le téléphone »](#-utilisation-depuis-le-téléphone-sans-pc)).
- **💻 En ligne de commande** — sur votre ordinateur (sections 1 à 5).

## Prérequis

- Python ≥ 3.9
- [ffmpeg](https://ffmpeg.org) installé (`sudo apt install ffmpeg` ou `brew install ffmpeg`)
- Un compte TikTok + une app sur le [portail développeur TikTok](https://developers.tiktok.com) (uniquement pour la publication automatique)

## Installation

```bash
git clone https://github.com/BuloJS/toktool && cd toktool
pip install .
```

## 1. Créer un clip (sans publication)

```bash
toktool clip "https://youtu.be/dQw4w9WgXcQ" --start 1:30 --duration 45
```

- `--start` : timecode de début — `90`, `1:30` ou `00:12:30`
- `--duration` : durée en secondes (ou `--end` pour un timecode de fin) — **plafonné à 60 s**
- `-o clip.mp4` : nom du fichier de sortie
- `--no-vertical` : garder le format d'origine (par défaut : 1080×1920 avec fond flouté)

Seule la section utile de la vidéo est téléchargée (pas la vidéo entière).

## 2. Connecter TikTok (une seule fois)

1. Sur [developers.tiktok.com](https://developers.tiktok.com), créez une app,
   activez le produit **Content Posting API** (scope `video.publish`) et
   déclarez l'URI de redirection `http://localhost:8763/callback`.
2. Exportez vos identifiants :

   ```bash
   export TIKTOK_CLIENT_KEY="votre_client_key"
   export TIKTOK_CLIENT_SECRET="votre_client_secret"
   ```

3. Lancez le flow OAuth (ouvre le navigateur, jetons stockés dans `~/.toktool/`) :

   ```bash
   toktool auth
   ```

Le jeton est rafraîchi automatiquement ensuite.

## 3. Suggestions de titre et de hashtags

À partir des métadonnées publiques de la vidéo (titre, description, tags,
catégorie), toktool propose plusieurs titres et une liste de hashtags —
sans rien télécharger :

```bash
toktool suggest "https://youtu.be/dQw4w9WgXcQ"
```

Exemple de sortie :

```
Titres proposés :
  1. Incroyable but de dernière minute en finale !
  2. Incroyable but de dernière minute en finale ! 🔥
  3. Le passage à ne pas rater : Incroyable But Dernière 👀
Hashtags proposés :
  #sport #football #highlights #but #finale #fyp #pourtoi #viral
```

## 4. Clip + publication TikTok en une commande

Avec un titre choisi manuellement :

```bash
toktool clip "https://youtu.be/dQw4w9WgXcQ" \
  --start 12:30 --duration 60 \
  --title "Le meilleur moment 😂 #clip #humour" \
  --publish
```

Ou en laissant toktool générer le titre + les hashtags automatiquement :

```bash
toktool clip "https://youtu.be/dQw4w9WgXcQ" \
  --start 12:30 --duration 60 --auto-title --publish
```

> 🔒 **Test en privé.** Par défaut, la publication se fait en `SELF_ONLY` :
> la vidéo arrive sur votre compte en « visible par moi uniquement ».
> Parfait pour un premier test — vous la vérifiez dans l'app TikTok, puis
> vous la passez en public à la main si elle vous convient. C'est aussi la
> seule visibilité autorisée tant que votre app TikTok n'est pas **auditée**.
> Après audit, ajoutez `--privacy PUBLIC_TO_EVERYONE` pour publier directement
> en public.

## 5. Planifier la publication

L'option `--at` fabrique le clip **tout de suite** (pour repérer aussitôt une
erreur) puis attend l'heure indiquée pour publier :

```bash
# Aujourd'hui ou demain à 18h00
toktool clip "https://youtu.be/dQw4w9WgXcQ" \
  --start 12:30 --auto-title --publish --at "18:00"

# Date et heure précises
toktool clip "https://youtu.be/dQw4w9WgXcQ" \
  --start 12:30 --auto-title --publish --at "2026-07-25 18:00"
```

Le processus reste ouvert jusqu'à la publication. Pour une planification qui
survit à la fermeture du terminal, passez par `cron` (macOS/Linux) :

```cron
# Publier tous les jours à 18h00 (crontab -e)
0 18 * * *  cd /chemin/vers/toktool && TIKTOK_CLIENT_KEY=... TIKTOK_CLIENT_SECRET=... \
            toktool clip "https://youtu.be/XXXX" --start 12:30 --auto-title --publish
```

## 📱 Utilisation depuis le téléphone, sans PC

Vous pouvez déclencher toktool comme une petite « app », directement depuis
**l'application mobile GitHub** — sans ligne de commande. GitHub Actions fait
tourner le téléchargement, la découpe et l'upload à votre place.

### Réglage initial (une seule fois, nécessite un ordinateur ou un Codespace)

Cette étape demande un navigateur une seule fois. Un **GitHub Codespace**
(bouton « Code → Codespaces » sur le repo) fonctionne aussi et s'ouvre depuis
le navigateur du téléphone.

1. **App TikTok.** Sur [developers.tiktok.com](https://developers.tiktok.com),
   créez une app, activez **Content Posting API** (scope `video.publish`), et
   déclarez l'URI de redirection `http://localhost:8763/callback`. Notez le
   *client key* et le *client secret*.

2. **Se connecter à TikTok** (dans le Codespace ou sur un PC) :

   ```bash
   pip install .
   export TIKTOK_CLIENT_KEY="..."  TIKTOK_CLIENT_SECRET="..."
   toktool auth --manual      # ouvre l'URL, vous collez l'URL de redirection
   toktool export             # affiche le JSON à copier
   ```

3. **Enregistrer 3 secrets** dans le repo GitHub
   (Settings → Secrets and variables → Actions → *New repository secret*) :

   | Nom du secret          | Valeur                                    |
   |------------------------|-------------------------------------------|
   | `TIKTOK_CLIENT_KEY`    | le client key TikTok                      |
   | `TIKTOK_CLIENT_SECRET` | le client secret TikTok                   |
   | `TIKTOK_CREDENTIALS`   | la ligne JSON affichée par `toktool export` |

C'est privé par nature : seuls vous (et les personnes à qui vous donnez accès
au repo) pouvez déclencher le workflow ou lire les secrets.

### Au quotidien (100 % téléphone)

1. Ouvrez le repo dans l'appli **GitHub** → onglet **Actions**.
2. Choisissez **🎬 Clip → TikTok** → **Run workflow**.
3. Remplissez le formulaire : URL YouTube, début, durée, titre (laissez vide
   pour un titre + hashtags générés automatiquement), visibilité, publier ou non.
4. **Run** — au bout de 1–2 min, la vidéo est sur votre TikTok (en privé par
   défaut). Le clip est aussi téléchargeable dans « Artifacts » pour le
   prévisualiser depuis le téléphone.

> Le jeton TikTok reste valable environ un an ; il suffit de refaire l'étape 2
> du réglage initial une fois par an.

## Droits d'auteur

Ne clippez et republiez que des contenus dont vous détenez les droits (vos
propres vidéos) ou pour lesquels vous avez l'autorisation du créateur. Le
reupload de contenus tiers viole les conditions d'utilisation de YouTube et
de TikTok.
