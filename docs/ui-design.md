# Desktop interface direction

de-Mail Desktop uses a sleek, modern, minimalist visual system appropriate for Windows. The
interface should feel calm and trustworthy while making archive safety and progress easy to read.

## Principles

- Use an almost entirely black palette. Roughly 98 percent of visible surfaces are black. White is
  reserved for text and icons, with a small amount of dark gray used for cards, borders, hover
  states, disabled controls, and visual separation.
- Do not rely on color for success, warning, or failure. Communicate state through explicit wording,
  icon shape, typography, and layout while maintaining accessible contrast.
- Prefer generous whitespace, short labels, clear typographic hierarchy, and one primary action
  per page.
- Use subtle dark-gray borders and elevation. Avoid ornamental gradients, excessive cards, visual noise,
  and phone-style stacked controls stretched across a desktop window.
- Keep the archive workflow linear and focused. Put advanced Gmail search and technical details
  behind deliberate disclosure controls.
- Show the fixed selected-message count throughout archive and verification. Never let animation
  or optimistic wording imply success before read-back verification completes.
- Use native-feeling keyboard navigation, focus indicators, high-DPI rendering, accessible color
  contrast, and layouts that remain usable with Windows text scaling.
- Prefer concise plain language. User-facing text must not contain em dash or en dash characters.

## Main window

A narrow navigation rail contains Archive Gmail, History, Reclaim storage, Report a problem, and
Settings. The content area uses a readable maximum width for forms and expands only views that
benefit from more space, such as history and progress details.

The archive flow moves through Connect, Select, Review exact count, Choose destination, Archive
progress, Verification, and Final report. A compact step indicator shows location without turning
the window into a wizard full of chrome.

Reclaim storage remains visibly unavailable until its separate safety milestone is implemented.
