import math
import os
import struct
import time
import time
import zlib


WIDTH = 1024
HEIGHT = 1024


def smooth(edge0, edge1, value):
    t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def chunk(kind, data):
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def hash_noise(x, y):
    value = (x * 374761393 + y * 668265263) & 0xFFFFFFFF
    value = ((value ^ (value >> 13)) * 1274126177) & 0xFFFFFFFF
    return (value ^ (value >> 16)) & 0xFFFFFFFF


def render():
    started = time.perf_counter()
    w, h = WIDTH, HEIGHT
    horizon = 0.68
    moon_x, moon_y, moon_r = 0.42, 0.36, 0.30
    boat_x, boat_y = 0.58, horizon + 0.001
    maria_marks = (
        (0.350, 0.303, 0.035, 0.047, 0.56),
        (0.420, 0.292, 0.030, 0.041, 0.48),
        (0.478, 0.342, 0.040, 0.027, 0.54),
        (0.386, 0.378, 0.025, 0.040, 0.46),
        (0.451, 0.403, 0.043, 0.029, 0.55),
        (0.337, 0.423, 0.026, 0.031, 0.43),
        (0.473, 0.389, 0.020, 0.025, 0.42),
    )
    craters = (
        (0.405, 0.330, 0.0040),
        (0.457, 0.365, 0.0032),
        (0.365, 0.390, 0.0037),
        (0.435, 0.430, 0.0030),
    )
    out = bytearray()

    for py in range(h):
        y = (py + 0.5) / h
        row = bytearray(w * 3)
        dy = y - horizon
        if y < horizon:
            sky_t = smooth(0.0, 0.87, y)
            sky_r = 8.0 + 8.0 * sky_t
            sky_g = 13.0 + 22.0 * sky_t
            sky_b = 34.0 + 35.0 * sky_t
        else:
            sea_t = min(1.0, dy / 0.48)
            sky_r = 7.0 + 12.0 * sea_t
            sky_g = 22.0 + 32.0 * sea_t
            sky_b = 43.0 + 39.0 * sea_t

        band = 0.5 + 0.5 * math.sin(dy * 330.0 + 0.52 * math.sin(dy * 29.0))
        band_gate = smooth(0.20, 0.82, band)
        fade = 1.0 - smooth(0.0, 0.30, max(0.0, dy))
        width_fade = 1.0 - 0.73 * max(0.0, dy) / (1.0 - horizon)
        phase = dy * 7.5
        drift = 0.009 * math.sin(dy * 48.0) + 0.004 * math.sin(dy * 15.0)
        seam = 1.0 - smooth(0.0007, 0.0045, abs(dy))

        for px in range(w):
            x = (px + 0.5) / w
            dx, my = x - moon_x, y - moon_y
            md2 = dx * dx + my * my
            md = math.sqrt(md2)
            halo = (1.0 - smooth(moon_r * 0.98, moon_r * 1.68, md)) * 0.25
            r = sky_r + 28.0 * halo
            g = sky_g + 23.0 * halo
            b = sky_b + 12.0 * halo
            # A restrained amber grade follows the moonlight into the upper-right.
            warm = halo * smooth(moon_x - 0.18, 0.88, x) * (1.0 - smooth(0.50, 0.95, y))
            r += 12.0 * warm
            g += 4.0 * warm
            b -= 5.0 * warm

            if md2 < (moon_r + 0.002) ** 2 and y < horizon:
                angle = math.atan2(my, dx)
                limb_wobble = 0.0022 * math.sin(angle * 3.0 + 0.4) + 0.0012 * math.sin(angle * 7.0 - 1.1)
                radius = moon_r * (1.0 + limb_wobble)
                moon = 1.0 - smooth(radius - 0.0012, radius + 0.0012, md)
                radial = md / moon_r
                light = 0.99 - 0.13 * smooth(0.50, 1.03, radial)
                upper_left = max(0.0, -(dx + my) * 1.8)
                rim = (1.0 - smooth(0.10, 0.52, radial)) * (0.035 + 0.12 * upper_left)
                mr = 248.0 * light + 18.0 * rim
                mg = 228.0 * light + 15.0 * rim
                mb = 185.0 * light + 10.0 * rim

                maria = 0.0
                for mx, mz, rx, ry, strength in maria_marks:
                    ex, ey = (x - mx) / rx, (y - mz) / ry
                    ellipse = math.sqrt(ex * ex + ey * ey)
                    mark = (1.0 - smooth(0.92, 1.08, ellipse)) * strength
                    maria = max(maria, mark)
                # Shallow inner shading gives the overlapping maria soft volume.
                shade = 0.0
                for mx, mz, rx, ry, strength in maria_marks:
                    ex, ey = (x - mx) / (rx * 1.55), (y - mz) / (ry * 1.55)
                    shade = max(shade, (1.0 - smooth(0.42, 1.20, math.sqrt(ex * ex + ey * ey))) * strength * 0.18)
                crater = 0.0
                for cx, cy, cr in craters:
                    cd = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                    crater = max(crater, 1.0 - smooth(cr * 0.62, cr, cd))
                dim = min(0.72, maria * 0.56 + shade + crater * 0.25)
                mr -= 48.0 * dim
                mg -= 43.0 * dim
                mb -= 33.0 * dim
                r = r * (1.0 - moon) + mr * moon
                g = g * (1.0 - moon) + mg * moon
                b = b * (1.0 - moon) + mb * moon

            if y >= horizon:
                r += 30.0 * seam
                g += 35.0 * seam
                b += 31.0 * seam
                if fade > 0.0:
                    wave = (math.sin(x * 35.0 + phase) + math.sin(x * 79.0 - phase * 0.63)) * 0.5
                    waviness = 1.0 + 0.075 * wave
                    edge = abs(x - moon_x - drift) / max(0.015, moon_r * width_fade * waviness)
                    across = 1.0 - smooth(0.67 + 0.035 * wave, 1.0 + 0.045 * wave, edge)
                    noise = hash_noise(px, py)
                    jitter = ((noise & 255) / 255.0 - 0.5) * 0.10
                    shimmer = max(0.0, band_gate * fade * across * (0.83 + 0.17 * wave + jitter))

                    # The hull blocks the reflected light; its short wake trails right.
                    gap = 0.0
                    if abs(x - boat_x) < 0.078 and dy < 0.045:
                        gap = 1.0 - smooth(0.050, 0.078, abs(x - boat_x))
                    wake_y = horizon + 0.018 + (x - boat_x) * 0.20
                    wake_d = abs(y - wake_y)
                    wake = (1.0 - smooth(0.002, 0.006, wake_d)) * (1.0 - smooth(0.025, 0.105, x - boat_x))
                    shimmer *= 1.0 - max(gap, wake * 0.72)
                    r += 137.0 * shimmer
                    g += 117.0 * shimmer
                    b += 82.0 * shimmer

            # Hull body lies between two gently curved SDF-like arcs.
            local = (x - boat_x) / 0.076
            if abs(local) < 1.0:
                top = boat_y + 0.004 - 0.011 * (1.0 - local * local)
                bottom = boat_y + 0.036 - 0.018 * (1.0 - local * local)
                if top <= y <= bottom:
                    r, g, b = 3.0, 4.0, 9.0
                if abs(y - top) < 0.0010:
                    r, g, b = 57.0, 43.0, 29.0

            # Seated, forward-leaning figure: head, hunched back, shoulder, and arm.
            head_d = math.sqrt((x - 0.559) ** 2 + (y - 0.653) ** 2) - 0.0085
            head = 1.0 - smooth(-0.0007, 0.0007, head_d)
            torso = 0.0
            for ax, ay, bx, by, radius in (
                (0.558, 0.662, 0.570, 0.675, 0.0062),
                (0.553, 0.666, 0.576, 0.671, 0.0045),
                (0.570, 0.669, 0.594, 0.683, 0.0017),
            ):
                vx, vy = bx - ax, by - ay
                q = max(0.0, min(1.0, ((x - ax) * vx + (y - ay) * vy) / (vx * vx + vy * vy)))
                sd = math.sqrt((x - ax - q * vx) ** 2 + (y - ay - q * vy) ** 2) - radius
                torso = max(torso, 1.0 - smooth(-0.0008, 0.0008, sd))

            # Long, thin oar crosses into the water at roughly twenty degrees.
            ax, ay, bx, by = 0.592, 0.682, 0.716, 0.727
            vx, vy = bx - ax, by - ay
            q = max(0.0, min(1.0, ((x - ax) * vx + (y - ay) * vy) / (vx * vx + vy * vy)))
            oar_d = math.sqrt((x - ax - q * vx) ** 2 + (y - ay - q * vy) ** 2)
            oar = 1.0 - smooth(0.0007, 0.0017, oar_d)
            if head > 0.0 or torso > 0.0 or oar > 0.0:
                figure = max(head, torso, oar)
                r *= 1.0 - figure
                g *= 1.0 - figure
                b *= 1.0 - figure
                if oar_d < 0.00075 and y < 0.690:
                    r += 36.0 * oar
                    g += 29.0 * oar
                    b += 20.0 * oar

            shore = smooth(0.947, 0.956, y)
            r = r * (1.0 - shore) + 4.0 * shore
            g = g * (1.0 - shore) + 6.0 * shore
            b = b * (1.0 - shore) + 12.0 * shore

            # Deterministic sparse stars vary subtly in size, tint, and intensity.
            if y < horizon and md > moon_r + 0.105:
                star_seed = hash_noise(px + 8191, py + 131071)
                cluster = 0.18 + 0.82 * (0.5 + 0.5 * math.sin(x * 31.0 + 0.8) * math.sin(y * 27.0))
                if (star_seed & 2047) < int(1.35 * cluster):
                    size = 0.6 + ((star_seed >> 11) & 255) / 255.0 * 0.8
                    brightness = 0.30 + ((star_seed >> 19) & 255) / 255.0 * 0.70
                    if size > 1.28:
                        brightness = min(1.0, brightness + 0.13)
                    tint = (star_seed >> 27) & 3
                    r += brightness * (48.0 if tint == 0 else 76.0)
                    g += brightness * (64.0 if tint == 0 else 70.0)
                    b += brightness * (86.0 if tint == 0 else 56.0)

            ex, ey = (x - 0.5) * 1.70, (y - 0.49) * 1.65
            vignette = 1.0 - 0.19 * smooth(0.48, 1.20, math.sqrt(ex * ex + ey * ey))
            noise = hash_noise(px, py)
            grain_seed = (noise >> 8) & 255
            if grain_seed < 26:
                grain = -3.0
            elif grain_seed < 82:
                grain = -1.0
            elif grain_seed < 174:
                grain = 0.0
            elif grain_seed < 230:
                grain = 1.0
            else:
                grain = 3.0
            r = max(0, min(255, int(r * vignette + grain)))
            g = max(0, min(255, int(g * vignette + grain)))
            b = max(0, min(255, int(b * vignette + grain)))
            i = px * 3
            row[i] = r
            row[i + 1] = g
            row[i + 2] = b

        out.extend(b"\x00")
        out.extend(row)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">2I5B", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(out, 9))
        + chunk(b"IEND", b"")
    )
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "entry.png")
    with open(path, "wb") as image_file:
        image_file.write(png)
    ihdr_width, ihdr_height = struct.unpack(">II", png[16:24])
    print(f"bytes={len(png)}")
    print(f"IHDR_dimensions={ihdr_width}x{ihdr_height}")
    print(f"render_seconds={time.perf_counter() - started:.3f}")


if __name__ == "__main__":
    render()
