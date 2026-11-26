#include <windows.h>

static BOOL wait_for_focus(HWND window, DWORD timeout_ms) {
    ULONGLONG deadline = GetTickCount64() + timeout_ms;
    MSG message;
    do {
        while (PeekMessageW(&message, NULL, 0, 0, PM_REMOVE)) {
            TranslateMessage(&message);
            DispatchMessageW(&message);
        }
        if (GetForegroundWindow() == window) {
            return TRUE;
        }
        Sleep(5);
    } while (GetTickCount64() < deadline);
    return FALSE;
}

int main(void) {
    HINSTANCE instance = GetModuleHandleW(NULL);

    WNDCLASSW window_class = {0};
    window_class.hInstance = instance;
    window_class.lpfnWndProc = DefWindowProcW;
    window_class.hbrBackground = (HBRUSH)GetStockObject(BLACK_BRUSH);
    window_class.lpszClassName = L"UmeYcFocusFixWindow";
    if (!RegisterClassW(&window_class)) {
        return 3;
    }
    HWND bridge = CreateWindowExW(
        0, window_class.lpszClassName, L"UmeYc-FocusFix", WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT, CW_USEDEFAULT, 900, 600, NULL, NULL, instance, NULL
    );
    if (bridge == NULL) {
        return 3;
    }

    ShowWindow(bridge, SW_SHOW);
    UpdateWindow(bridge);
    SetWindowPos(bridge, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW);
    BringWindowToTop(bridge);
    SetForegroundWindow(bridge);
    BOOL switched = wait_for_focus(bridge, 350);
    if (switched) {
        Sleep(10);
    }
    DestroyWindow(bridge);
    Sleep(50);
    return switched ? 0 : 4;
}
