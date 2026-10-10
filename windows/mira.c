/* YXI96 Mira: punto de mira para Windows. Un solo ejecutable, sin instalador. */

#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN

#include <windows.h>
#include <commctrl.h>
#include <shlobj.h>
#include <math.h>
#include <stdio.h>
#include <stdint.h>

#define STYLE_PUNTO 0
#define STYLE_CRUZ 1
#define STYLE_ABIERTA 2
#define STYLE_CIRCULO 3
#define STYLE_CIRCULO_PUNTO 4
#define STYLE_CRUZ_CIRCULO 5
#define STYLE_MARCAS 6
#define STYLE_CUADRADO 7
#define STYLE_COUNT 8

#define ID_STYLE 101
#define ID_SIZE 102
#define ID_THICK 103
#define ID_OPACITY 104
#define ID_OFFX 105
#define ID_OFFY 106
#define ID_OUTLINE 107
#define ID_TOGGLE 108
#define ID_CENTER 109
#define ID_PREVIEW 110
#define ID_COLOR 120
#define ID_LBL_SIZE 140
#define ID_LBL_THICK 141
#define ID_LBL_OPACITY 142
#define ID_LBL_OFFX 143
#define ID_LBL_OFFY 144

#define MAX_SIDE 360
#define HOTKEY_TOGGLE 1

static const wchar_t *kStyleNames[STYLE_COUNT] = {
    L"Punto", L"Cruz", L"Cruz abierta", L"Círculo",
    L"Círculo y punto", L"Cruz y círculo", L"Marcas", L"Cuadrado"};

static const COLORREF kColors[6] = {
    RGB(255, 255, 255), RGB(0x39, 0xFF, 0x6A), RGB(0xFF, 0x4D, 0x4D),
    RGB(0x4D, 0xE2, 0xFF), RGB(0xFF, 0xE1, 0x4D), RGB(0xFF, 0x4D, 0xFF)};

static int g_dpi = 96;
static HWND g_panel;
static HWND g_overlay;
static HFONT g_font;
static HFONT g_title;
static HBRUSH g_bg;
static HBRUSH g_panel_brush;
static HINSTANCE g_inst;
static uint8_t g_rgba[MAX_SIDE * MAX_SIDE * 4];
static int g_side;

static int g_style = STYLE_PUNTO;
static int g_size = 6;
static int g_thick = 2;
static int g_opacity = 100;
static COLORREF g_color = RGB(255, 255, 255);
static int g_outline = 1;
static int g_offx = 0;
static int g_offy = 0;
static int g_visible = 1;

static int S(int px) { return MulDiv(px, g_dpi, 96); }

static int clampi(int value, int low, int high) {
    if (value < low) return low;
    if (value > high) return high;
    return value;
}

static float maxf(float a, float b) { return a > b ? a : b; }
static float minf(float a, float b) { return a < b ? a : b; }

static int byteu(float value) {
    if (value <= 0.f) return 0;
    if (value >= 255.f) return 255;
    return (int)(value + 0.5f);
}

static float coverage(float margin) {
    const float aa = 0.8f;
    float amount = (margin + aa) / (2.f * aa);
    if (amount <= 0.f) return 0.f;
    if (amount >= 1.f) return 1.f;
    return amount * amount * (3.f - 2.f * amount);
}

static float dist_cross(float x, float y, float length) {
    float ax = fabsf(x);
    float ay = fabsf(y);
    float horizontal = hypotf(maxf(ax - length, 0.f), ay);
    float vertical = hypotf(ax, maxf(ay - length, 0.f));
    return minf(horizontal, vertical);
}

static float dist_arm(float along, float across, float start, float outer) {
    if (along < start) return hypotf(start - along, across);
    if (along > outer) return hypotf(along - outer, across);
    return across;
}

static float dist_arms(float x, float y, float start, float arm) {
    float outer = start + arm;
    float horizontal = dist_arm(fabsf(x), fabsf(y), start, outer);
    float vertical = dist_arm(fabsf(y), fabsf(x), start, outer);
    return minf(horizontal, vertical);
}

static float dist_square(float x, float y, float half) {
    float ax = fabsf(x);
    float ay = fabsf(y);
    if (ax <= half && ay <= half) return minf(half - ax, half - ay);
    return hypotf(ax - minf(ax, half), ay - minf(ay, half));
}

static float punto_radius(void) {
    return maxf(1.2f, g_size * 0.55f + g_thick * 0.35f);
}

static float dot_radius(void) {
    float natural = maxf(1.3f, g_thick * 0.9f);
    float cap = maxf(1.3f, g_size * 0.34f);
    return minf(natural, cap);
}

static void open_geom(float *start, float *arm) {
    float hole = maxf(3.f, g_size * 0.30f);
    *start = hole + g_thick / 2.f;
    *arm = maxf(4.f, (float)g_size);
}

static void mark_geom(float *start, float *arm) {
    float hole = maxf(4.f, g_size * 0.70f);
    *start = hole + g_thick / 2.f;
    *arm = maxf(3.f, g_size * 0.42f);
}

static float shape_margin(float x, float y) {
    float half = g_thick / 2.f;
    float start, arm, ring, dot, cross;
    switch (g_style) {
    case STYLE_PUNTO:
        return punto_radius() - hypotf(x, y);
    case STYLE_CRUZ:
        return half - dist_cross(x, y, (float)g_size);
    case STYLE_ABIERTA:
        open_geom(&start, &arm);
        return half - dist_arms(x, y, start, arm);
    case STYLE_CIRCULO:
        return half - fabsf(hypotf(x, y) - (float)g_size);
    case STYLE_CIRCULO_PUNTO:
        ring = half - fabsf(hypotf(x, y) - (float)g_size);
        dot = dot_radius() - hypotf(x, y);
        return maxf(ring, dot);
    case STYLE_CRUZ_CIRCULO:
        cross = half - dist_cross(x, y, (float)g_size);
        ring = half - fabsf(hypotf(x, y) - (float)g_size);
        return maxf(cross, ring);
    case STYLE_MARCAS:
        mark_geom(&start, &arm);
        return half - dist_arms(x, y, start, arm);
    case STYLE_CUADRADO:
        return half - dist_square(x, y, (float)g_size);
    default:
        return punto_radius() - hypotf(x, y);
    }
}

static float reach_of(void) {
    float pad = g_thick / 2.f + (g_outline ? 2.4f : 1.4f);
    float start, arm;
    if (g_style == STYLE_PUNTO) return punto_radius() + pad;
    if (g_style == STYLE_ABIERTA) {
        open_geom(&start, &arm);
        return start + arm + pad;
    }
    if (g_style == STYLE_MARCAS) {
        mark_geom(&start, &arm);
        return start + arm + pad;
    }
    return (float)g_size + pad;
}

static int render_rgba(void) {
    float reach = reach_of();
    int side = (int)ceilf(reach * 2.f) + 1;
    if (side < 3) side = 3;
    if (side % 2 == 0) side += 1;
    if (side > MAX_SIDE) side = (MAX_SIDE & 1) ? MAX_SIDE : MAX_SIDE - 1;
    int red = GetRValue(g_color);
    int green = GetGValue(g_color);
    int blue = GetBValue(g_color);
    float outline_px = g_outline ? 1.35f : 0.f;
    float opacity = g_opacity / 100.f;
    float center = (side - 1) / 2.f;
    memset(g_rgba, 0, (size_t)side * side * 4);
    for (int row = 0; row < side; row++) {
        float y = row - center;
        for (int col = 0; col < side; col++) {
            float margin = shape_margin(col - center, y);
            float fill = coverage(margin);
            float under = outline_px ? coverage(margin + outline_px) : 0.f;
            if (fill <= 0.f && under <= 0.f) continue;
            float under_a = under * 0.92f;
            float covered = fill + under_a * (1.f - fill);
            if (covered <= 0.004f) continue;
            float out_r = red * fill / covered;
            float out_g = green * fill / covered;
            float out_b = blue * fill / covered;
            int index = (row * side + col) * 4;
            g_rgba[index] = (uint8_t)byteu(out_r);
            g_rgba[index + 1] = (uint8_t)byteu(out_g);
            g_rgba[index + 2] = (uint8_t)byteu(out_b);
            g_rgba[index + 3] = (uint8_t)byteu(covered * opacity * 255.f);
        }
    }
    g_side = side;
    return side;
}

static void settings_file(wchar_t *out) {
    wchar_t base[MAX_PATH];
    base[0] = 0;
    if (FAILED(SHGetFolderPathW(NULL, CSIDL_APPDATA, NULL, 0, base)) || !base[0]) {
        GetEnvironmentVariableW(L"APPDATA", base, MAX_PATH);
    }
    wchar_t dir[MAX_PATH];
    _snwprintf(dir, MAX_PATH, L"%s\\YXI96Mira", base);
    CreateDirectoryW(dir, NULL);
    _snwprintf(out, MAX_PATH, L"%s\\mira.ini", dir);
}

static void clamp_settings(void) {
    g_style = clampi(g_style, 0, STYLE_COUNT - 1);
    g_size = clampi(g_size, 2, 64);
    g_thick = clampi(g_thick, 1, 14);
    g_opacity = clampi(g_opacity, 10, 100);
    g_offx = clampi(g_offx, -200, 200);
    g_offy = clampi(g_offy, -200, 200);
    g_outline = g_outline ? 1 : 0;
    g_visible = g_visible ? 1 : 0;
}

static void load_settings(void) {
    wchar_t path[MAX_PATH];
    settings_file(path);
    g_style = GetPrivateProfileIntW(L"mira", L"style", STYLE_PUNTO, path);
    g_size = GetPrivateProfileIntW(L"mira", L"size", 6, path);
    g_thick = GetPrivateProfileIntW(L"mira", L"thickness", 2, path);
    g_opacity = GetPrivateProfileIntW(L"mira", L"opacity", 100, path);
    g_color = (COLORREF)GetPrivateProfileIntW(L"mira", L"color", RGB(255, 255, 255), path);
    g_outline = GetPrivateProfileIntW(L"mira", L"outline", 1, path);
    g_offx = GetPrivateProfileIntW(L"mira", L"offset_x", 0, path);
    g_offy = GetPrivateProfileIntW(L"mira", L"offset_y", 0, path);
    g_visible = GetPrivateProfileIntW(L"mira", L"visible", 1, path);
    clamp_settings();
}

static void save_settings(void) {
    wchar_t path[MAX_PATH];
    wchar_t buf[32];
    settings_file(path);
    clamp_settings();
    _snwprintf(buf, 32, L"%d", g_style);
    WritePrivateProfileStringW(L"mira", L"style", buf, path);
    _snwprintf(buf, 32, L"%d", g_size);
    WritePrivateProfileStringW(L"mira", L"size", buf, path);
    _snwprintf(buf, 32, L"%d", g_thick);
    WritePrivateProfileStringW(L"mira", L"thickness", buf, path);
    _snwprintf(buf, 32, L"%d", g_opacity);
    WritePrivateProfileStringW(L"mira", L"opacity", buf, path);
    _snwprintf(buf, 32, L"%u", (unsigned)g_color);
    WritePrivateProfileStringW(L"mira", L"color", buf, path);
    _snwprintf(buf, 32, L"%d", g_outline);
    WritePrivateProfileStringW(L"mira", L"outline", buf, path);
    _snwprintf(buf, 32, L"%d", g_offx);
    WritePrivateProfileStringW(L"mira", L"offset_x", buf, path);
    _snwprintf(buf, 32, L"%d", g_offy);
    WritePrivateProfileStringW(L"mira", L"offset_y", buf, path);
    _snwprintf(buf, 32, L"%d", g_visible);
    WritePrivateProfileStringW(L"mira", L"visible", buf, path);
}

static void enable_dpi(void) {
    HMODULE shcore = LoadLibraryW(L"shcore.dll");
    if (shcore) {
        typedef HRESULT(WINAPI * SetFn)(int);
        SetFn set = (SetFn)GetProcAddress(shcore, "SetProcessDpiAwareness");
        if (set) {
            set(2);
            return;
        }
    }
    SetProcessDPIAware();
}

static void read_dpi(HWND hwnd) {
    typedef UINT(WINAPI * DpiFn)(HWND);
    DpiFn fn = (DpiFn)GetProcAddress(GetModuleHandleW(L"user32.dll"), "GetDpiForWindow");
    if (fn && hwnd) {
        UINT dpi = fn(hwnd);
        if (dpi >= 96) g_dpi = (int)dpi;
        return;
    }
    HDC dc = GetDC(NULL);
    int dpi = GetDeviceCaps(dc, LOGPIXELSX);
    ReleaseDC(NULL, dc);
    if (dpi >= 96) g_dpi = dpi;
}

static HWND add_label(HWND parent, const wchar_t *text, int x, int y, int w, int h, int id) {
    HWND hwnd = CreateWindowExW(0, L"STATIC", text, WS_CHILD | WS_VISIBLE | (id ? SS_RIGHT : SS_LEFT),
                                x, y, w, h, parent, (HMENU)(INT_PTR)id, g_inst, NULL);
    SendMessageW(hwnd, WM_SETFONT, (WPARAM)g_font, TRUE);
    return hwnd;
}

static void set_value_label(int id, int value, const wchar_t *suffix) {
    wchar_t buf[32];
    _snwprintf(buf, 32, L"%d %s", value, suffix);
    SetWindowTextW(GetDlgItem(g_panel, id), buf);
}

static void refresh_labels(void) {
    set_value_label(ID_LBL_SIZE, g_size, L"px");
    set_value_label(ID_LBL_THICK, g_thick, L"px");
    set_value_label(ID_LBL_OPACITY, g_opacity, L"%");
    set_value_label(ID_LBL_OFFX, g_offx, L"px");
    set_value_label(ID_LBL_OFFY, g_offy, L"px");
    SetWindowTextW(GetDlgItem(g_panel, ID_TOGGLE), g_visible ? L"Ocultar mira" : L"Mostrar mira");
}

static void paint_overlay(void) {
    if (!g_overlay) return;
    if (!g_visible) {
        ShowWindow(g_overlay, SW_HIDE);
        return;
    }
    int side = render_rgba();
    HMONITOR monitor = MonitorFromWindow(g_panel ? g_panel : g_overlay, MONITOR_DEFAULTTOPRIMARY);
    MONITORINFO info;
    info.cbSize = sizeof(info);
    if (!GetMonitorInfoW(monitor, &info)) {
        info.rcMonitor.left = 0;
        info.rcMonitor.top = 0;
        info.rcMonitor.right = GetSystemMetrics(SM_CXSCREEN);
        info.rcMonitor.bottom = GetSystemMetrics(SM_CYSCREEN);
    }
    int left = (info.rcMonitor.left + info.rcMonitor.right) / 2 + g_offx - side / 2;
    int top = (info.rcMonitor.top + info.rcMonitor.bottom) / 2 + g_offy - side / 2;

    BITMAPINFO bi;
    memset(&bi, 0, sizeof(bi));
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth = side;
    bi.bmiHeader.biHeight = -side;
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    void *bits = NULL;
    HDC screen = GetDC(NULL);
    HDC memory = CreateCompatibleDC(screen);
    HBITMAP dib = CreateDIBSection(screen, &bi, DIB_RGB_COLORS, &bits, NULL, 0);
    if (dib && bits) {
        uint8_t *dst = (uint8_t *)bits;
        for (int i = 0; i < side * side; i++) {
            uint8_t r = g_rgba[i * 4];
            uint8_t g = g_rgba[i * 4 + 1];
            uint8_t b = g_rgba[i * 4 + 2];
            uint8_t a = g_rgba[i * 4 + 3];
            dst[i * 4] = (uint8_t)(b * a / 255);
            dst[i * 4 + 1] = (uint8_t)(g * a / 255);
            dst[i * 4 + 2] = (uint8_t)(r * a / 255);
            dst[i * 4 + 3] = a;
        }
        HGDIOBJ old = SelectObject(memory, dib);
        POINT origin = {0, 0};
        POINT dest = {left, top};
        SIZE size = {side, side};
        BLENDFUNCTION blend;
        blend.BlendOp = AC_SRC_OVER;
        blend.BlendFlags = 0;
        blend.SourceConstantAlpha = 255;
        blend.AlphaFormat = AC_SRC_ALPHA;
        UpdateLayeredWindow(g_overlay, screen, &dest, &size, memory, &origin, 0, &blend, ULW_ALPHA);
        SelectObject(memory, old);
    }
    if (dib) DeleteObject(dib);
    DeleteDC(memory);
    ReleaseDC(NULL, screen);
    ShowWindow(g_overlay, SW_SHOWNOACTIVATE);
    SetWindowPos(g_overlay, HWND_TOPMOST, left, top, side, side, SWP_NOACTIVATE | SWP_SHOWWINDOW);
}

static void nudge_overlay(void) {
    if (g_overlay && g_visible && IsWindowVisible(g_overlay)) {
        SetWindowPos(g_overlay, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
    }
}

static void apply_change(void) {
    clamp_settings();
    refresh_labels();
    InvalidateRect(GetDlgItem(g_panel, ID_PREVIEW), NULL, TRUE);
    for (int i = 0; i < 6; i++) InvalidateRect(GetDlgItem(g_panel, ID_COLOR + i), NULL, TRUE);
    InvalidateRect(GetDlgItem(g_panel, ID_TOGGLE), NULL, TRUE);
    paint_overlay();
    save_settings();
}

static void read_controls(void) {
    g_style = (int)SendMessageW(GetDlgItem(g_panel, ID_STYLE), CB_GETCURSEL, 0, 0);
    g_size = (int)SendMessageW(GetDlgItem(g_panel, ID_SIZE), TBM_GETPOS, 0, 0);
    g_thick = (int)SendMessageW(GetDlgItem(g_panel, ID_THICK), TBM_GETPOS, 0, 0);
    g_opacity = (int)SendMessageW(GetDlgItem(g_panel, ID_OPACITY), TBM_GETPOS, 0, 0);
    g_offx = (int)SendMessageW(GetDlgItem(g_panel, ID_OFFX), TBM_GETPOS, 0, 0) - 200;
    g_offy = (int)SendMessageW(GetDlgItem(g_panel, ID_OFFY), TBM_GETPOS, 0, 0) - 200;
    g_outline = (int)SendMessageW(GetDlgItem(g_panel, ID_OUTLINE), BM_GETCHECK, 0, 0) == BST_CHECKED;
    apply_change();
}

static void push_controls(void) {
    SendMessageW(GetDlgItem(g_panel, ID_STYLE), CB_SETCURSEL, (WPARAM)g_style, 0);
    SendMessageW(GetDlgItem(g_panel, ID_SIZE), TBM_SETPOS, TRUE, g_size);
    SendMessageW(GetDlgItem(g_panel, ID_THICK), TBM_SETPOS, TRUE, g_thick);
    SendMessageW(GetDlgItem(g_panel, ID_OPACITY), TBM_SETPOS, TRUE, g_opacity);
    SendMessageW(GetDlgItem(g_panel, ID_OFFX), TBM_SETPOS, TRUE, g_offx + 200);
    SendMessageW(GetDlgItem(g_panel, ID_OFFY), TBM_SETPOS, TRUE, g_offy + 200);
    SendMessageW(GetDlgItem(g_panel, ID_OUTLINE), BM_SETCHECK, g_outline ? BST_CHECKED : BST_UNCHECKED, 0);
    refresh_labels();
}

static HWND make_slider(HWND parent, int id, int x, int y, int w, int low, int high, int pos) {
    HWND bar = CreateWindowExW(0, TRACKBAR_CLASSW, L"", WS_CHILD | WS_VISIBLE | TBS_HORZ | TBS_NOTICKS,
                               x, y, w, S(28), parent, (HMENU)(INT_PTR)id, g_inst, NULL);
    SendMessageW(bar, TBM_SETRANGEMIN, FALSE, low);
    SendMessageW(bar, TBM_SETRANGEMAX, TRUE, high);
    SendMessageW(bar, TBM_SETPOS, TRUE, pos);
    return bar;
}

static void draw_round_button(const DRAWITEMSTRUCT *item, COLORREF fill, COLORREF text, const wchar_t *caption) {
    HBRUSH brush = CreateSolidBrush(fill);
    FillRect(item->hDC, &item->rcItem, brush);
    DeleteObject(brush);
    SetBkMode(item->hDC, TRANSPARENT);
    SetTextColor(item->hDC, text);
    SelectObject(item->hDC, g_font);
    DrawTextW(item->hDC, caption, -1, (RECT *)&item->rcItem, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
}

static void paint_preview(const DRAWITEMSTRUCT *item) {
    RECT box = item->rcItem;
    HBRUSH frame = CreateSolidBrush(RGB(17, 28, 40));
    FillRect(item->hDC, &box, frame);
    DeleteObject(frame);
    int side = render_rgba();
    BITMAPINFO bi;
    memset(&bi, 0, sizeof(bi));
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth = side;
    bi.bmiHeader.biHeight = -side;
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    void *bits = NULL;
    HDC memory = CreateCompatibleDC(item->hDC);
    HBITMAP dib = CreateDIBSection(item->hDC, &bi, DIB_RGB_COLORS, &bits, NULL, 0);
    if (!dib || !bits) {
        DeleteDC(memory);
        return;
    }
    uint8_t *dst = (uint8_t *)bits;
    for (int y = 0; y < side; y++) {
        for (int x = 0; x < side; x++) {
            int src = (y * side + x) * 4;
            int light = ((x / 8) + (y / 8)) % 2 == 0;
            int br = light ? 54 : 24;
            int bg = light ? 70 : 30;
            int bb = light ? 82 : 36;
            float a = g_rgba[src + 3] / 255.f;
            int i = src;
            dst[i] = (uint8_t)byteu(g_rgba[src + 2] * a + bb * (1.f - a));
            dst[i + 1] = (uint8_t)byteu(g_rgba[src + 1] * a + bg * (1.f - a));
            dst[i + 2] = (uint8_t)byteu(g_rgba[src] * a + br * (1.f - a));
            dst[i + 3] = 255;
        }
    }
    HGDIOBJ old = SelectObject(memory, dib);
    int avail_w = box.right - box.left - S(12);
    int avail_h = box.bottom - box.top - S(12);
    int draw = side;
    if (draw > avail_w) draw = avail_w;
    if (draw > avail_h) draw = avail_h;
    if (draw < 1) draw = 1;
    int dx = box.left + ((box.right - box.left) - draw) / 2;
    int dy = box.top + ((box.bottom - box.top) - draw) / 2;
    SetStretchBltMode(item->hDC, HALFTONE);
    StretchBlt(item->hDC, dx, dy, draw, draw, memory, 0, 0, side, side, SRCCOPY);
    SelectObject(memory, old);
    DeleteObject(dib);
    DeleteDC(memory);
}

static LRESULT CALLBACK panel_proc(HWND hwnd, UINT msg, WPARAM wparam, LPARAM lparam) {
    switch (msg) {
    case WM_ERASEBKGND: {
        RECT rect;
        GetClientRect(hwnd, &rect);
        FillRect((HDC)wparam, &rect, g_bg);
        return 1;
    }
    case WM_CTLCOLORSTATIC: {
        HDC dc = (HDC)wparam;
        SetTextColor(dc, RGB(233, 244, 245));
        SetBkColor(dc, RGB(9, 16, 25));
        return (LRESULT)g_bg;
    }
    case WM_HSCROLL:
        read_controls();
        return 0;
    case WM_COMMAND: {
        int id = LOWORD(wparam);
        int code = HIWORD(wparam);
        if (id == ID_STYLE && code == CBN_SELCHANGE) {
            read_controls();
            return 0;
        }
        if (id == ID_OUTLINE) {
            read_controls();
            return 0;
        }
        if (id == ID_TOGGLE) {
            g_visible = !g_visible;
            apply_change();
            return 0;
        }
        if (id == ID_CENTER) {
            g_offx = 0;
            g_offy = 0;
            push_controls();
            apply_change();
            return 0;
        }
        if (id >= ID_COLOR && id < ID_COLOR + 6) {
            g_color = kColors[id - ID_COLOR];
            apply_change();
            return 0;
        }
        return 0;
    }
    case WM_DRAWITEM: {
        const DRAWITEMSTRUCT *item = (const DRAWITEMSTRUCT *)lparam;
        int id = (int)wparam;
        if (id == ID_PREVIEW) {
            paint_preview(item);
            return TRUE;
        }
        if (id == ID_TOGGLE) {
            wchar_t caption[64];
            GetWindowTextW(item->hwndItem, caption, 64);
            draw_round_button(item, RGB(69, 230, 189), RGB(6, 37, 38), caption);
            return TRUE;
        }
        if (id == ID_CENTER) {
            draw_round_button(item, RGB(28, 48, 64), RGB(233, 244, 245), L"Centrar");
            return TRUE;
        }
        if (id >= ID_COLOR && id < ID_COLOR + 6) {
            COLORREF color = kColors[id - ID_COLOR];
            HBRUSH brush = CreateSolidBrush(color);
            FillRect(item->hDC, &item->rcItem, brush);
            DeleteObject(brush);
            int selected = color == g_color;
            HPEN pen = CreatePen(PS_SOLID, S(selected ? 3 : 1), selected ? RGB(69, 230, 189) : RGB(42, 59, 72));
            HGDIOBJ old = SelectObject(item->hDC, pen);
            SelectObject(item->hDC, GetStockObject(NULL_BRUSH));
            Rectangle(item->hDC, item->rcItem.left, item->rcItem.top, item->rcItem.right, item->rcItem.bottom);
            SelectObject(item->hDC, old);
            DeleteObject(pen);
            return TRUE;
        }
        break;
    }
    case WM_HOTKEY:
        if (wparam == HOTKEY_TOGGLE) {
            g_visible = !g_visible;
            apply_change();
        }
        return 0;
    case WM_KEYDOWN:
        if (wparam == VK_F8) {
            g_visible = !g_visible;
            apply_change();
            return 0;
        }
        break;
    case WM_MOVE:
        paint_overlay();
        return 0;
    case WM_TIMER:
        nudge_overlay();
        return 0;
    case WM_DESTROY:
        KillTimer(hwnd, 1);
        UnregisterHotKey(hwnd, HOTKEY_TOGGLE);
        save_settings();
        if (g_overlay) DestroyWindow(g_overlay);
        PostQuitMessage(0);
        return 0;
    default:
        break;
    }
    return DefWindowProcW(hwnd, msg, wparam, lparam);
}

static LRESULT CALLBACK overlay_proc(HWND hwnd, UINT msg, WPARAM wparam, LPARAM lparam) {
    return DefWindowProcW(hwnd, msg, wparam, lparam);
}

static void create_panel(void) {
    RECT work;
    SystemParametersInfoW(SPI_GETWORKAREA, 0, &work, 0);
    g_panel = CreateWindowExW(0, L"YXI96MiraPanel", L"YXI96 Mira",
                              WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
                              work.right - 200, work.top + 24, 200, 200, NULL, NULL, g_inst, NULL);
    read_dpi(g_panel);
    RECT wanted = {0, 0, S(440), S(680)};
    AdjustWindowRect(&wanted, WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX, FALSE);
    int w = wanted.right - wanted.left;
    int h = wanted.bottom - wanted.top;
    int x = work.right - w - S(24);
    int y = work.top + S(24);
    SetWindowPos(g_panel, NULL, x, y, w, h, SWP_NOZORDER | SWP_NOACTIVATE);

    int pad = S(18);
    int inner = w - GetSystemMetrics(SM_CXFRAME) * 2 - pad * 2;
    RECT client;
    GetClientRect(g_panel, &client);
    inner = client.right - pad * 2;
    int cy = pad;

    HWND title = add_label(g_panel, L"YXI96 Mira", pad, cy, inner, S(28), 0);
    SendMessageW(title, WM_SETFONT, (WPARAM)g_title, TRUE);
    cy += S(30);
    add_label(g_panel, L"Punto de mira encima de la pantalla. El clic lo atraviesa.", pad, cy, inner, S(20), 0);
    cy += S(28);
    add_label(g_panel, L"ESTILO", pad, cy, inner, S(16), 0);
    cy += S(18);
    HWND combo = CreateWindowExW(0, L"COMBOBOX", L"", WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST | WS_VSCROLL,
                                 pad, cy, inner, S(240), g_panel, (HMENU)ID_STYLE, g_inst, NULL);
    SendMessageW(combo, WM_SETFONT, (WPARAM)g_font, TRUE);
    for (int i = 0; i < STYLE_COUNT; i++) SendMessageW(combo, CB_ADDSTRING, 0, (LPARAM)kStyleNames[i]);
    cy += S(32);

    struct {
        const wchar_t *caption;
        int id;
        int label;
        int low;
        int high;
        int value;
        const wchar_t *suffix;
    } rows[] = {
        {L"Tamaño", ID_SIZE, ID_LBL_SIZE, 2, 64, g_size, L"px"},
        {L"Grosor", ID_THICK, ID_LBL_THICK, 1, 14, g_thick, L"px"},
        {L"Transparencia", ID_OPACITY, ID_LBL_OPACITY, 10, 100, g_opacity, L"%"},
        {L"Centro horizontal", ID_OFFX, ID_LBL_OFFX, 0, 400, g_offx + 200, L"px"},
        {L"Centro vertical", ID_OFFY, ID_LBL_OFFY, 0, 400, g_offy + 200, L"px"},
    };
    for (int i = 0; i < 5; i++) {
        add_label(g_panel, rows[i].caption, pad, cy, S(180), S(16), 0);
        add_label(g_panel, L"", pad + inner - S(70), cy, S(70), S(16), rows[i].label);
        cy += S(16);
        make_slider(g_panel, rows[i].id, pad, cy, inner, rows[i].low, rows[i].high, rows[i].value);
        cy += S(30);
    }

    add_label(g_panel, L"COLOR", pad, cy, inner, S(16), 0);
    cy += S(20);
    int chip = S(36);
    for (int i = 0; i < 6; i++) {
        CreateWindowExW(0, L"BUTTON", L"", WS_CHILD | WS_VISIBLE | BS_OWNERDRAW, pad + i * (chip + S(8)), cy, chip,
                        S(28), g_panel, (HMENU)(INT_PTR)(ID_COLOR + i), g_inst, NULL);
    }
    cy += S(40);
    HWND check = CreateWindowExW(0, L"BUTTON", L"Contorno oscuro", WS_CHILD | WS_VISIBLE | BS_AUTOCHECKBOX, pad, cy,
                                 inner, S(22), g_panel, (HMENU)ID_OUTLINE, g_inst, NULL);
    SendMessageW(check, WM_SETFONT, (WPARAM)g_font, TRUE);
    cy += S(32);
    CreateWindowExW(0, L"BUTTON", L"Ocultar mira", WS_CHILD | WS_VISIBLE | BS_OWNERDRAW, pad, cy, S(140), S(34),
                    g_panel, (HMENU)ID_TOGGLE, g_inst, NULL);
    CreateWindowExW(0, L"BUTTON", L"Centrar", WS_CHILD | WS_VISIBLE | BS_OWNERDRAW, pad + S(152), cy, S(110), S(34),
                    g_panel, (HMENU)ID_CENTER, g_inst, NULL);
    cy += S(46);
    CreateWindowExW(0, L"STATIC", L"", WS_CHILD | WS_VISIBLE | SS_OWNERDRAW, pad, cy, inner, S(110), g_panel,
                    (HMENU)ID_PREVIEW, g_inst, NULL);
    cy += S(118);
    HWND hint = add_label(g_panel, L"Ctrl+Alt+M oculta la mira aunque el juego esté delante.", pad, cy, inner, S(40), 0);
    (void)hint;
    push_controls();
}

static void register_classes(void) {
    WNDCLASSW panel = {0};
    panel.lpfnWndProc = panel_proc;
    panel.hInstance = g_inst;
    panel.lpszClassName = L"YXI96MiraPanel";
    panel.hCursor = LoadCursorW(NULL, IDC_ARROW);
    panel.hbrBackground = g_bg;
    RegisterClassW(&panel);

    WNDCLASSW overlay = {0};
    overlay.lpfnWndProc = overlay_proc;
    overlay.hInstance = g_inst;
    overlay.lpszClassName = L"YXI96MiraOverlay";
    RegisterClassW(&overlay);
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE prev, PWSTR cmd, int show) {
    (void)prev;
    (void)cmd;
    (void)show;
    g_inst = instance;
    enable_dpi();

    HANDLE mutex = CreateMutexW(NULL, TRUE, L"Local\\YXI96Mira");
    if (GetLastError() == ERROR_ALREADY_EXISTS) {
        HWND existing = FindWindowW(L"YXI96MiraPanel", NULL);
        if (existing) {
            ShowWindow(existing, SW_RESTORE);
            SetForegroundWindow(existing);
        }
        return 0;
    }

    INITCOMMONCONTROLSEX controls = {sizeof(controls), ICC_BAR_CLASSES | ICC_STANDARD_CLASSES};
    InitCommonControlsEx(&controls);
    load_settings();
    g_bg = CreateSolidBrush(RGB(9, 16, 25));
    g_panel_brush = CreateSolidBrush(RGB(17, 28, 40));
    g_font = CreateFontW(-16, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS,
                         CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    g_title = CreateFontW(-22, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS,
                          CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    register_classes();
    create_panel();

    g_overlay = CreateWindowExW(WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
                                L"YXI96MiraOverlay", L"YXI96 Mira", WS_POPUP, 0, 0, 10, 10, NULL, NULL, instance, NULL);
    paint_overlay();
    RegisterHotKey(g_panel, HOTKEY_TOGGLE, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, 'M');
    SetTimer(g_panel, 1, 400, NULL);
    ShowWindow(g_panel, SW_SHOWNORMAL);
    UpdateWindow(g_panel);
    apply_change();

    MSG message;
    while (GetMessageW(&message, NULL, 0, 0) > 0) {
        TranslateMessage(&message);
        DispatchMessageW(&message);
    }
    if (mutex) {
        ReleaseMutex(mutex);
        CloseHandle(mutex);
    }
    return 0;
}
