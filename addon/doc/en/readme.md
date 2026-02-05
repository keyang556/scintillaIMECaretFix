# Scintilla IME Composition Caret Fix

## Summary

This NVDA add-on fixes the issue where caret movements within IME composition strings are not announced correctly in Scintilla-based editors like Notepad++.

## Problem Description

Since NVDA 2022.1, when using an Input Method Editor (IME) to input Chinese, Japanese, Korean, or other CJK characters in Scintilla-based editors (such as Notepad++), NVDA fails to:

- Display the composition string on the braille display while typing
- Announce the correct character when navigating within uncommitted composition strings using arrow keys
- Update the braille display with the correct character during composition navigation

Instead, NVDA announces "blank" for every arrow key press within the composition string, and the braille display shows no feedback during typing.

These issues are tracked at:
- https://github.com/nvaccess/nvda/issues/14140 (No braille feedback when typing)
- https://github.com/nvaccess/nvda/issues/14152 (Caret navigation not announced)

## Solution

This add-on manually tracks the cursor position within IME composition strings and announces the correct character when navigating with arrow keys. It:

1. Detects when the user is in a Scintilla control with an active IME composition
2. Intercepts left and right arrow key presses
3. Tracks the cursor position within the composition string
4. Announces the appropriate character via speech and braille

## Compatibility

- Minimum NVDA version: 2022.1
- Tested with: Notepad++, and other Scintilla-based editors
- Tested IME: Microsoft Bopomofo (Traditional Chinese)

## Usage

Simply install the add-on and use your IME as normal in Notepad++ or other Scintilla-based editors. When you type characters and use arrow keys to navigate within the uncommitted composition string, NVDA will now correctly announce each character.

## Changelog

### Version 1.1

- Updated build configuration for proper add-on packaging
- Added Traditional Chinese localization for manifest
- Improved documentation

### Version 1.0

- Initial release
- Fixes IME composition navigation in Scintilla editors
- Fixes braille display not showing composition string while typing (#14140)
