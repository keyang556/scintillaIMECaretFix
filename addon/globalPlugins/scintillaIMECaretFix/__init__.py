# Scintilla IME Composition Caret Fix
# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2024 NVDA Add-on Developer
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

"""
Global plugin to fix NVDA failing to track caret movements within IME composition
strings in Scintilla-based editors like Notepad++.

This fixes issues:
- https://github.com/nvaccess/nvda/issues/14140 (No braille feedback when typing composition string)
- https://github.com/nvaccess/nvda/issues/14152 (Caret navigation not announced)

Approach: Monitor NVDA's InputComposition object and manually track cursor position
within the composition string, since Scintilla doesn't expose the cursor position
via InputComposition.selectionStart or caretOffset. Also monitors composition string
changes to provide braille feedback during typing.
"""

import globalPluginHandler
import api
import speech
import braille
import winUser
import inputCore
from logHandler import log
import wx
import core
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
	"""Global plugin that monitors Scintilla controls for IME composition navigation and braille output."""

	def __init__(self):
		super().__init__()
		self._compositionString = ""
		self._cursorPos = 0  # Manually tracked cursor position
		self._lastCompObjId = None  # To detect new compositions
		self._pollTimer = None  # Timer for polling composition changes
		self._lastPolledComposition = ""  # Last composition string seen during polling
		self._isMonitoring = False  # Flag to track if we're actively monitoring
		# Register our gesture filter
		inputCore.decide_executeGesture.register(self._onGesture)
		# Register focus event handler
		core.postNvdaStartup.register(self._registerFocusHandler)
		log.debug("ScintillaIME: Plugin initialized (manual cursor tracking + braille monitoring)")

	def _registerFocusHandler(self):
		"""Register the focus change handler after NVDA is fully started."""
		try:
			from visionEnhancementProviders import screenCurtain
		except ImportError:
			pass
		# Hook into focus events
		import eventHandler
		self._oldFocusHandler = getattr(eventHandler, '_handleFocusChange', None)
		log.debug("ScintillaIME: Focus handler registered")

	def terminate(self):
		try:
			inputCore.decide_executeGesture.unregister(self._onGesture)
		except Exception:
			pass
		try:
			core.postNvdaStartup.unregister(self._registerFocusHandler)
		except Exception:
			pass
		self._stopCompositionPolling()
		super().terminate()

	def _startCompositionPolling(self):
		"""Start polling for composition string changes."""
		if self._pollTimer is None:
			self._pollTimer = wx.CallLater(50, self._pollCompositionChanges)
			self._isMonitoring = True
			log.debug("ScintillaIME: Started composition polling")

	def _stopCompositionPolling(self):
		"""Stop polling for composition string changes."""
		if self._pollTimer is not None:
			try:
				self._pollTimer.Stop()
			except Exception:
				pass
			self._pollTimer = None
		self._isMonitoring = False
		self._lastPolledComposition = ""
		log.debug("ScintillaIME: Stopped composition polling")

	def _pollCompositionChanges(self):
		"""Poll for changes to the composition string and update braille."""
		try:
			focus = api.getFocusObject()
			if not focus or not isScintillaWindow(focus):
				self._stopCompositionPolling()
				return

			compObj = getInputCompositionObject(focus)
			if compObj and hasattr(compObj, 'compositionString') and compObj.compositionString:
				currentComp = compObj.compositionString
				# Check if composition string changed (new character typed)
				if currentComp != self._lastPolledComposition:
					log.debug(f"ScintillaIME: Composition changed from '{self._lastPolledComposition}' to '{currentComp}'")
					# Update braille to show the full composition string
					braille.handler.message(currentComp)
					self._lastPolledComposition = currentComp
				# Continue polling
				self._pollTimer = wx.CallLater(50, self._pollCompositionChanges)
			else:
				# No more composition, stop polling
				self._stopCompositionPolling()
		except Exception as e:
			log.debugWarning(f"ScintillaIME: Error polling composition: {e}")
			self._stopCompositionPolling()


	def _onGesture(self, gesture, *args, **kwargs):
		"""Filter gestures to detect arrow keys during IME composition and start braille monitoring."""
		try:
			# First, check if we should start braille monitoring for any keystroke
			focus = api.getFocusObject()
			if focus and isScintillaWindow(focus):
				compObj = getInputCompositionObject(focus)
				if compObj and hasattr(compObj, 'compositionString') and compObj.compositionString:
					# Start polling for braille updates if not already monitoring
					if not self._isMonitoring:
						self._startCompositionPolling()

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
