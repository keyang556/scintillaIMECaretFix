# Scintilla IME Composition Caret Fix
# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2024 NVDA Add-on Developer
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

"""
Global plugin to fix NVDA failing to track caret movements within IME composition
strings in Scintilla-based editors like Notepad++.

This fixes issue: https://github.com/nvaccess/nvda/issues/14152

Approach: Monitor NVDA's InputComposition object and manually track cursor position
within the composition string, since Scintilla doesn't expose the cursor position
via InputComposition.selectionStart or caretOffset.
"""

import globalPluginHandler
import api
import speech
import braille
import winUser
import inputCore
from logHandler import log
import wx
from NVDAObjects import inputComposition


def isScintillaWindow(obj):
	"""Check if the object is in a Scintilla control."""
	if not obj:
		return False
	try:
		hwnd = obj.windowHandle if hasattr(obj, 'windowHandle') else None
		if hwnd:
			className = winUser.getClassName(hwnd)
			return className and "Scintilla" in className
		return False
	except Exception:
		return False


def getInputCompositionObject(obj):
	"""Get the InputComposition object if present."""
	# Check if the object itself is an InputComposition
	if isinstance(obj, inputComposition.InputComposition):
		return obj
	# Check parent chain
	parent = obj.parent if hasattr(obj, 'parent') else None
	while parent:
		if isinstance(parent, inputComposition.InputComposition):
			return parent
		parent = parent.parent if hasattr(parent, 'parent') else None
	return None


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""Global plugin that monitors Scintilla controls for IME composition navigation."""

	def __init__(self):
		super().__init__()
		self._compositionString = ""
		self._cursorPos = 0  # Manually tracked cursor position
		self._lastCompObjId = None  # To detect new compositions
		# Register our gesture filter
		inputCore.decide_executeGesture.register(self._onGesture)
		log.debug("ScintillaIME: Plugin initialized (manual cursor tracking)")

	def terminate(self):
		try:
			inputCore.decide_executeGesture.unregister(self._onGesture)
		except Exception:
			pass
		super().terminate()

	def _onGesture(self, gesture, *args, **kwargs):
		"""Filter gestures to detect arrow keys during IME composition."""
		try:
			# Check if this is a left or right arrow key
			arrowDirection = 0  # -1 for left, +1 for right
			if hasattr(gesture, 'vkCode'):
				if gesture.vkCode == 0x25:  # Left arrow
					arrowDirection = -1
				elif gesture.vkCode == 0x27:  # Right arrow
					arrowDirection = 1
			elif hasattr(gesture, 'mainKeyName'):
				if gesture.mainKeyName == 'leftArrow':
					arrowDirection = -1
				elif gesture.mainKeyName == 'rightArrow':
					arrowDirection = 1
			
			if arrowDirection != 0:
				# Check if we're in a Scintilla with active composition
				focus = api.getFocusObject()
				if focus and isScintillaWindow(focus):
					compObj = getInputCompositionObject(focus)
					if compObj and hasattr(compObj, 'compositionString') and compObj.compositionString:
						compString = compObj.compositionString
						compObjId = id(compObj)
						
						# Check if this is a new composition
						if compObjId != self._lastCompObjId or compString != self._compositionString:
							# New composition, reset cursor to end
							self._lastCompObjId = compObjId
							self._compositionString = compString
							self._cursorPos = len(compString)
							log.debug(f"ScintillaIME: New composition '{compString}', cursor at {self._cursorPos}")
						
						# Calculate new cursor position
						newPos = self._cursorPos + arrowDirection
						
						# Clamp to valid range
						if 0 <= newPos <= len(compString):
							self._cursorPos = newPos
							log.debug(f"ScintillaIME: Cursor moved to {self._cursorPos} in '{compString}'")
							
							# Schedule announcement
							wx.CallAfter(self._announceCharacter, compString, self._cursorPos, arrowDirection)
						else:
							log.debug(f"ScintillaIME: Cursor at boundary, pos={self._cursorPos}, len={len(compString)}")
				
		except Exception as e:
			log.debugWarning(f"ScintillaIME: Error in gesture filter: {e}")
		
		return True

	def _announceCharacter(self, compString, cursorPos, direction):
		"""Announce the character at or before cursor position."""
		try:
			if not compString:
				return
			
			# Determine which character to announce
			char = None
			if direction < 0:  # Left arrow
				# Moving left: announce character at new cursor position
				if 0 <= cursorPos < len(compString):
					char = compString[cursorPos]
					log.debug(f"ScintillaIME: Left -> char '{char}' at pos {cursorPos}")
			else:  # Right arrow
				# Moving right: announce character we just passed (pos-1)
				charPos = cursorPos - 1
				if 0 <= charPos < len(compString):
					char = compString[charPos]
					log.debug(f"ScintillaIME: Right -> char '{char}' at pos {charPos}")
			
			if char:
				# Delay announcement to override NVDA's default "空白" speech
				# NVDA's EditableText fires caret events ~20-30ms after our handler
				# We wait 150ms to ensure we speak AFTER NVDA's default processing
				wx.CallLater(150, self._doAnnounce, char)
					
		except Exception as e:
			log.error(f"ScintillaIME: Error announcing character: {e}")

	def _doAnnounce(self, char):
		"""Actually speak and braille the character."""
		try:
			log.debug(f"ScintillaIME: Speaking '{char}'")
			# Cancel any pending speech (like "空白") before we speak
			speech.cancelSpeech()
			speech.speakText(char)
			braille.handler.message(char)
		except Exception as e:
			log.error(f"ScintillaIME: Error in _doAnnounce: {e}")
