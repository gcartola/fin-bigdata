import base64
from collections import Counter, deque
from io import BytesIO
from pathlib import Path

import streamlit as st

import app_bigdados as app

_ORIGINAL_AUTH_GATE = app.render_auth_gate


def _color_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def _dominant_edge_colors(image, sample_step: int = 6, max_colors: int = 8) -> list[tuple[int, int, int]]:
    width, height = image.size
    pixels = image.load()
    samples = []

    for x in range(0, width, sample_step):
        for y in (0, height - 1):
            r, g, b, a = pixels[x, y]
            if a:
                samples.append((r // 8 * 8, g // 8 * 8, b // 8 * 8))
    for y in range(0, height, sample_step):
        for x in (0, width - 1):
            r, g, b, a = pixels[x, y]
            if a:
                samples.append((r // 8 * 8, g // 8 * 8, b // 8 * 8))

    return [color for color, _ in Counter(samples).most_common(max_colors)]


def _remove_background_connected_to_edges(image, bg_colors: list[tuple[int, int, int]], tolerance: int = 72):
    width, height = image.size
    pixels = image.load()
    queue = deque()
    visited = set()

    def is_background(x: int, y: int) -> bool:
        r, g, b, a = pixels[x, y]
        if a == 0:
            return True
        color = (r, g, b)
        return any(_color_distance(color, bg) <= tolerance for bg in bg_colors)

    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))

    while queue:
        x, y = queue.popleft()
        if x < 0 or y < 0 or x >= width or y >= height or (x, y) in visited:
            continue
        visited.add((x, y))
        if not is_background(x, y):
            continue
        r, g, b, _ = pixels[x, y]
        pixels[x, y] = (r, g, b, 0)
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))


def _remove_internal_background_holes(image, bg_colors: list[tuple[int, int, int]], tolerance: int = 58):
    width, height = image.size
    pixels = image.load()
    for y in range(height):
        y_ratio = y / height
        for x in range(width):
            x_ratio = x / width
            r, g, b, a = pixels[x, y]
            if not a:
                continue
            color = (r, g, b)
            looks_like_edge_bg = any(_color_distance(color, bg) <= tolerance for bg in bg_colors)
            is_dark_matte = max(color) < 46 and abs(r - g) < 18 and abs(g - b) < 18
            is_center_lower_hole = 0.35 <= x_ratio <= 0.65 and 0.28 <= y_ratio <= 0.78
            if looks_like_edge_bg or (is_center_lower_hole and is_dark_matte):
                pixels[x, y] = (r, g, b, 0)


def clean_logo_asset() -> str:
    source = next(
        (
            path
            for path in [
                Path("assets/icon-bd.png"),
                Path("assets/logo_bd.png"),
                Path("assets/bigdados-logo.png"),
                Path("assets/bigdados_logo.png"),
            ]
            if path.exists() and path.is_file()
        ),
        None,
    )
    if not source:
        return app.BIGDADOS_LOGO_BASE64

    try:
        from PIL import Image

        image = Image.open(source).convert("RGBA")
        bg_colors = _dominant_edge_colors(image)
        _remove_background_connected_to_edges(image, bg_colors, tolerance=78)
        _remove_internal_background_holes(image, bg_colors, tolerance=64)

        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception:
        return app.BIGDADOS_LOGO_BASE64


app.BIGDADOS_LOGO_BASE64 = clean_logo_asset()
app.BIGDADOS_FAVICON_BASE64 = app.BIGDADOS_LOGO_BASE64


def inject_auth_visual_refinement():
    st.markdown(
        """
        <style>
          .bigdados-auth-shell {
            width: min(448px, 92vw) !important;
            max-width: 448px !important;
            margin-top: 8vh !important;
            gap: 12px !important;
          }

          .bigdados-login-logo {
            width: min(180px, 34vw) !important;
            max-height: 138px !important;
            margin-bottom: 2px !important;
          }

          .bigdados-auth-card {
            width: 100% !important;
            box-sizing: border-box !important;
            padding: 20px 22px !important;
            background: color-mix(in srgb, var(--secondary-background-color) 74%, transparent) !important;
            border-color: color-mix(in srgb, var(--text-color) 12%, transparent) !important;
          }

          .bigdados-auth-title {
            font-size: 23px !important;
          }

          .bigdados-auth-subtitle {
            font-size: 13px !important;
            font-weight: 560 !important;
            color: color-mix(in srgb, var(--text-color) 80%, transparent) !important;
          }

          main div[data-testid="stTextInput"],
          main div[data-testid="stButton"] {
            width: min(448px, 92vw) !important;
            max-width: 448px !important;
            margin-left: auto !important;
            margin-right: auto !important;
          }

          main .stAlert {
            width: min(448px, 92vw) !important;
            max-width: 448px !important;
            margin-left: auto !important;
            margin-right: auto !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_auth_gate_refined() -> bool:
    inject_auth_visual_refinement()
    return _ORIGINAL_AUTH_GATE()


app.render_auth_gate = render_auth_gate_refined
app.base_app.render_auth_gate = render_auth_gate_refined

if __name__ == "__main__":
    app.main()
