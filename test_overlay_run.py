from PIL import Image
from utils.image_overlay import save_image_with_quote

src = 'images/previews/post_preview_71509232_3.jpg'
out = 'images/previews/post_preview_71509232_3_overlay.jpg'
try:
    img = Image.open(src)
    save_image_with_quote(img, "Trust the quiet courage in your heart. It holds the compass to guide you toward your brightest, unfolding potential.", out)
    print('Saved overlay:', out)
except Exception as e:
    print('Test failed:', e)
