"""Génère l'icône de l'app parent (bus blanc sur dégradé bleu de marque).

Cohérent avec le brand mark de `lib/screens/login_screen.dart` (#2563EB → #4F46E5).
Le bus est construit comme un MASQUE (255 = blanc, 0 = évidé) : c'est ce qui permet
de « percer » les vitres et les phares pour laisser voir le dégradé.

Usage : python tool/generate_icon.py   (puis `dart run flutter_launcher_icons`)
"""
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
BRAND_A = (37, 99, 235)   # #2563EB
BRAND_B = (79, 70, 229)   # #4F46E5

OUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "icon"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def gradient(size: int) -> Image.Image:
    """Dégradé diagonal (haut-gauche → bas-droite)."""
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            px[x, y] = (
                round(BRAND_A[0] + (BRAND_B[0] - BRAND_A[0]) * t),
                round(BRAND_A[1] + (BRAND_B[1] - BRAND_A[1]) * t),
                round(BRAND_A[2] + (BRAND_B[2] - BRAND_A[2]) * t),
            )
    return img


def bus_mask(size: int) -> Image.Image:
    """Masque du bus : 255 = carrosserie, 0 = fond et évidements."""
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)

    # Roues (dessinées d'abord, dépassent sous la carrosserie)
    for cx in (392, 632):
        d.ellipse((cx - 66, 654, cx + 66, 786), fill=255)

    # Carrosserie
    d.rounded_rectangle((262, 214, 762, 706), radius=76, fill=255)

    # Bandeau de vitres (évidé)
    d.rounded_rectangle((320, 286, 704, 452), radius=36, fill=0)
    # Montant central entre les deux vitres
    d.rectangle((494, 286, 530, 452), fill=255)

    # Phares (évidés)
    d.rounded_rectangle((330, 566, 424, 616), radius=22, fill=0)
    d.rounded_rectangle((600, 566, 694, 616), radius=22, fill=0)

    # Calandre / pare-chocs (évidé)
    d.rounded_rectangle((424, 648, 600, 682), radius=16, fill=0)

    return m


def main() -> None:
    white = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 255))
    mask = bus_mask(SIZE)

    # Icône complète : dégradé + bus blanc appliqué via le masque
    icon = gradient(SIZE).convert("RGBA")
    icon.paste(white, (0, 0), mask)
    icon.save(OUT_DIR / "app_icon.png")

    # Foreground adaptative Android : bus seul sur fond transparent, rétréci
    # (Android rogne ~33 % sur les bords selon le masque du lanceur).
    fg = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    fg.paste(white, (0, 0), mask)
    scaled = fg.resize((int(SIZE * 0.60), int(SIZE * 0.60)), Image.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    off = (SIZE - scaled.width) // 2
    canvas.paste(scaled, (off, off), scaled)
    canvas.save(OUT_DIR / "app_icon_foreground.png")

    print(f"OK -> {OUT_DIR / 'app_icon.png'}")
    print(f"OK -> {OUT_DIR / 'app_icon_foreground.png'}")


if __name__ == "__main__":
    main()
