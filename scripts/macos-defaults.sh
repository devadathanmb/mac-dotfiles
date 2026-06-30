#!/usr/bin/env bash
set -euo pipefail

# Apply macOS defaults converted from ansible/roles/macos/tasks/main.yml.
# Safe to re-run. Does not require sudo.

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script is intended for macOS only." >&2
  exit 1
fi

log() {
  printf '\n==> %s\n' "$1"
}

write_default() {
  local domain="$1"
  local key="$2"
  local type="$3"
  local value="$4"

  if ! defaults write "$domain" "$key" "-$type" "$value"; then
    echo "Warning: could not write $domain $key; skipping." >&2
  fi
}

write_current_host_default() {
  local domain="$1"
  local key="$2"
  local type="$3"
  local value="$4"

  if ! defaults -currentHost write "$domain" "$key" "-$type" "$value"; then
    echo "Warning: could not write currentHost $domain $key; skipping." >&2
  fi
}

log "Trackpad settings"
write_default NSGlobalDomain com.apple.trackpad.scaling float 1.5
write_default com.apple.AppleMultitouchTrackpad Clicking bool true
write_current_host_default NSGlobalDomain com.apple.mouse.tapBehavior int 1
write_default com.apple.AppleMultitouchTrackpad TrackpadRightClick bool true
write_default com.apple.AppleMultitouchTrackpad TrackpadThreeFingerDrag bool false
write_default com.apple.AppleMultitouchTrackpad FirstClickThreshold int 1
write_default com.apple.AppleMultitouchTrackpad SecondClickThreshold int 1
write_default com.apple.AppleMultitouchTrackpad ForceSuppressed bool false
write_default com.apple.AppleMultitouchTrackpad ActuateDetents bool true
write_default com.apple.AppleMultitouchTrackpad DragLock int 0
write_default com.apple.AppleMultitouchTrackpad Dragging int 0
write_default com.apple.AppleMultitouchTrackpad TrackpadCornerSecondaryClick int 0
write_default com.apple.AppleMultitouchTrackpad TrackpadFiveFingerPinchGesture int 2
write_default com.apple.AppleMultitouchTrackpad TrackpadFourFingerHorizSwipeGesture int 2
write_default com.apple.AppleMultitouchTrackpad TrackpadFourFingerPinchGesture int 2
write_default com.apple.AppleMultitouchTrackpad TrackpadFourFingerVertSwipeGesture int 2
write_default com.apple.AppleMultitouchTrackpad TrackpadHandResting int 1
write_default com.apple.AppleMultitouchTrackpad TrackpadHorizScroll int 1
write_default com.apple.AppleMultitouchTrackpad TrackpadMomentumScroll bool true
write_default com.apple.AppleMultitouchTrackpad TrackpadPinch bool true
write_default com.apple.AppleMultitouchTrackpad TrackpadRotate bool true
write_default com.apple.AppleMultitouchTrackpad TrackpadScroll int 1
write_default com.apple.AppleMultitouchTrackpad TrackpadThreeFingerHorizSwipeGesture int 2
write_default com.apple.AppleMultitouchTrackpad TrackpadThreeFingerTapGesture int 0
write_default com.apple.AppleMultitouchTrackpad TrackpadThreeFingerVertSwipeGesture int 2
write_default com.apple.AppleMultitouchTrackpad TrackpadTwoFingerDoubleTapGesture bool true
write_default com.apple.AppleMultitouchTrackpad TrackpadTwoFingerFromRightEdgeSwipeGesture int 3
write_default com.apple.AppleMultitouchTrackpad USBMouseStopsTrackpad int 0
write_default NSGlobalDomain com.apple.trackpad.forceClick int 1
write_default NSGlobalDomain com.apple.springing.enabled bool true
write_default NSGlobalDomain com.apple.springing.delay float 0.5

log "Finder settings"
write_default NSGlobalDomain AppleShowAllExtensions bool true
write_default com.apple.finder _FXShowPosixPathInTitle bool true
write_default com.apple.finder CreateDesktop bool false
write_default com.apple.finder FXEnableExtensionChangeWarning bool false
write_default com.apple.finder FXDefaultSearchScope string SCcf
write_default com.apple.finder ShowStatusBar bool true
write_default com.apple.finder ShowPathbar bool true
write_default com.apple.finder FXPreferredViewStyle string Nlsv
write_default com.apple.finder WarnOnEmptyTrash bool false
write_default com.apple.finder NewWindowTarget string PfHm
write_default com.apple.finder FXICloudDriveDesktop bool false
write_default com.apple.finder FXICloudDriveDocuments bool false
write_default com.apple.finder FXRemoveOldTrashItems bool true
write_default com.apple.finder ShowRecentTags bool false
mkdir -p "$HOME/Library"
chmod 0755 "$HOME/Library"
chflags nohidden "$HOME/Library" 2>/dev/null || true

log "Keyboard and text input settings"
write_default NSGlobalDomain NSAutomaticSpellingCorrectionEnabled bool false
write_default NSGlobalDomain KeyRepeat int 1
write_default NSGlobalDomain InitialKeyRepeat int 10
write_default NSGlobalDomain ApplePressAndHoldEnabled bool false
write_default NSGlobalDomain NSAutomaticCapitalizationEnabled bool true
write_default NSGlobalDomain NSAutomaticPeriodSubstitutionEnabled bool true
write_default NSGlobalDomain NSAutomaticQuoteSubstitutionEnabled bool false
write_default NSGlobalDomain NSAutomaticDashSubstitutionEnabled bool false
write_default NSGlobalDomain AppleKeyboardUIMode int 2
write_default NSGlobalDomain NSNavPanelExpandedStateForSaveMode bool true
write_default NSGlobalDomain NSNavPanelExpandedStateForSaveMode2 bool true

log "Appearance settings"
write_default NSGlobalDomain AppleInterfaceStyle string Dark
write_default NSGlobalDomain AppleAccentColor int 4
write_default NSGlobalDomain AppleHighlightColor string "0.752941 0.964706 0.678431 Green"
write_default NSGlobalDomain AppleMenuBarVisibleInFullscreen int 0
write_default NSGlobalDomain AppleMiniaturizeOnDoubleClick bool false

log "Dock and window manager settings"
write_default com.apple.dock autohide bool true
write_default com.apple.dock mineffect string scale
write_default com.apple.dock minimize-to-application bool true
write_default com.apple.dock show-process-indicators bool true
write_default com.apple.dock static-only bool true
write_default com.apple.dock launchanim bool false
write_default com.apple.dock show-recents bool false
write_default com.apple.dock expose-animation-duration float 0.1
write_default com.apple.dock mru-spaces bool false
write_default com.apple.dock tilesize int 52
write_default com.apple.dock expose-group-apps bool false
write_default com.apple.dock enterMissionControlByTopWindowDrag bool true
write_default com.apple.WindowManager EnableStandardClickToShowDesktop bool false
write_default com.apple.WindowManager EnableTiledWindowMargins bool false
write_default com.apple.WindowManager StandardHideWidgets bool true
write_default com.apple.WindowManager AppWindowGroupingBehavior int 1
write_default com.apple.dock wvous-tr-corner int 0
write_default com.apple.dock wvous-tr-modifier int 0

log "Terminal, menu bar, and screenshot settings"
if ! defaults write com.apple.terminal StringEncodings -array 4; then
  echo "Warning: could not write com.apple.terminal StringEncodings; skipping." >&2
fi
write_current_host_default com.apple.controlcenter BatteryShowPercentage bool true
write_current_host_default com.apple.controlcenter Sound int 18
write_current_host_default com.apple.controlcenter Bluetooth int 2
write_current_host_default com.apple.controlcenter Display int 8
write_current_host_default com.apple.controlcenter NowPlaying int 8
write_default NSGlobalDomain com.apple.sound.beep.feedback int 1
write_default NSGlobalDomain AppleICUForce24HourTime bool true
write_current_host_default NSGlobalDomain NSStatusItemSpacing int 12
write_current_host_default NSGlobalDomain NSStatusItemSelectionPadding int 12
mkdir -p "$HOME/Pictures/Screenshots"
chmod 0755 "$HOME/Pictures/Screenshots"
write_default com.apple.screencapture location string "$HOME/Pictures/Screenshots"
write_default com.apple.screencapture type string png
write_default com.apple.screencapture disable-shadow bool true

log "Performance settings"
write_default NSGlobalDomain NSDisableAutomaticTermination bool true

log "Spaces settings"
write_default com.apple.spaces spans-displays bool false
write_default NSGlobalDomain AppleSpacesSwitchOnActivate bool true

log "App settings"
write_default com.apple.TextEdit RichText bool false
write_default com.apple.TextEdit PlainTextEncoding int 4
write_default com.apple.TextEdit PlainTextEncodingForWrite int 4
write_default com.apple.ActivityMonitor ShowCategory int 100
write_default com.apple.ActivityMonitor SortColumn string CPUUsage
write_default com.apple.ActivityMonitor SortDirection int 0

log "Restarting affected services"
killall Dock 2>/dev/null || true
killall Finder 2>/dev/null || true
killall SystemUIServer 2>/dev/null || true
killall cfprefsd 2>/dev/null || true

log "Done. Some settings may require logging out or restarting to fully apply."
