# Vision

Lets EON see and describe the screen: "what's on my screen", "what does
this error say", "describe this window".

## Flow

```
ScreenCapturer.capture()          -> ScreenCapture (JPEG bytes + window title)
VisionAnalyzer.analyze(capture)   -> str (sent to a vision-capable Ollama model)
VisionManager.describe_screen()   -> VisionResult (what the action executor uses)
```

`VisionManager` is the only entry point other modules should use.

## Requirements

- `Pillow` (`pip install Pillow`) for screen capture.
- `pywin32` (already used elsewhere in EON, e.g. shortcut resolution)
  for reading the active window's title. Optional — vision still works
  without it, just without window-title context.
- A vision-capable model pulled in Ollama, e.g.:

  ```
  ollama pull llava
  ```

  The default text model (`qwen2.5:3b` in `config/models.json`) is
  **not** vision-capable — `VisionConfig.model` is deliberately
  separate.

## Config

`config/settings.json`:

- `vision_enabled` (default `true`) — master switch, separate from
  `automation_enabled` since a user may want app-launching without
  screen capture, or vice versa.
- `vision_model` (default `"llava"`) — which Ollama model to use.

## Not yet built

- Locating/clicking specific on-screen elements (would need something
  like `pyautogui` plus coordinate-grounded model output).
- Webcam input.
- Continuous/ambient watching (currently capture is only on-demand,
  triggered by a user request).
