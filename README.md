# toktool

Agent en ligne de commande : vous donnez une **URL YouTube** et un **timecode**,
il crée un **clip de 60 s maximum** (format vertical 9:16 prêt pour TikTok)
et peut le **publier automatiquement sur TikTok** via l'API officielle.

```
URL YouTube + timecode ──> yt-dlp ──> ffmpeg (découpe + 9:16) ──> TikTok
```

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

## 3. Clip + publication TikTok en une commande

```bash
toktool clip "https://youtu.be/dQw4w9WgXcQ" \
  --start 12:30 --duration 60 \
  --title "Le meilleur moment 😂 #clip #humour" \
  --publish
```

> ⚠️ Tant que votre app TikTok n'est pas **auditée** par TikTok, l'API impose
> la visibilité `SELF_ONLY` : la vidéo arrive sur votre compte en « visible
> par moi uniquement », à basculer en public depuis l'app TikTok. Après audit
> de votre app, ajoutez `--privacy PUBLIC_TO_EVERYONE` pour publier directement
> en public.

## Droits d'auteur

Ne clippez et republiez que des contenus dont vous détenez les droits (vos
propres vidéos) ou pour lesquels vous avez l'autorisation du créateur. Le
reupload de contenus tiers viole les conditions d'utilisation de YouTube et
de TikTok.
