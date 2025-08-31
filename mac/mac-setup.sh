#!/usr/bin/env bash

# ==============================================================================
# macOS System Configuration Script
# ==============================================================================
# This script configures various macOS system preferences and settings
# ==============================================================================

echo "🚀 Starting macOS system configuration..."
echo "📝 This script will configure trackpad, finder, keyboard, dock, and other system settings"
echo "⚠️  Some changes may require a logout or restart to take full effect"
echo ""

# ==============================================================================
# SYSTEM PREPARATION
# ==============================================================================

echo "🔧 Preparing system..."

# Close any open System Preferences panes to prevent them from overriding
# settings we're about to change
osascript -e 'tell application "System Preferences" to quit'

echo "✅ System preparation complete"
echo ""

# ==============================================================================
# TRACKPAD SETTINGS
# ==============================================================================

echo "👆 Configuring trackpad settings..."

# Enable tap to click
defaults write com.apple.AppleMultitouchTrackpad Clicking -bool true
defaults -currentHost write NSGlobalDomain com.apple.mouse.tapBehavior -int 1

# Enable right-click with two fingers
defaults write com.apple.AppleMultitouchTrackpad TrackpadRightClick -bool true

# Enable three-finger drag
defaults write com.apple.AppleMultitouchTrackpad TrackpadThreeFingerDrag -bool true

echo "✅ Trackpad configuration complete"
echo ""

# ==============================================================================
# FINDER SETTINGS
# ==============================================================================

echo "📁 Configuring Finder settings..."

# Show all filename extensions
defaults write NSGlobalDomain AppleShowAllExtensions -bool true

# Show full POSIX path in Finder window title
defaults write com.apple.finder _FXShowPosixPathInTitle -bool true

# Hide all desktop icons
defaults write com.apple.finder CreateDesktop -bool false

# Disable warning before changing a file extension
defaults write com.apple.finder FXEnableExtensionChangeWarning -bool false

# Set default search scope in Finder to current folder
defaults write com.apple.finder FXDefaultSearchScope -string "SCcf"

# Show status bar
defaults write com.apple.finder ShowStatusBar -bool true

# Show path bar
defaults write com.apple.finder ShowPathbar -bool true

# Use list view as default
defaults write com.apple.finder FXPreferredViewStyle -string "Nlsv"

# Disable warning before emptying Trash
defaults write com.apple.finder WarnOnEmptyTrash -bool false

# Show ~/Library folder
chflags nohidden ~/Library

echo "✅ Finder configuration complete"
echo ""

# ==============================================================================
# KEYBOARD AND TEXT INPUT SETTINGS
# ==============================================================================

echo "⌨️  Configuring keyboard and text input settings..."

# Disable automatic spelling correction
defaults write NSGlobalDomain NSAutomaticSpellingCorrectionEnabled -bool false

# Set fast key repeat rate
defaults write NSGlobalDomain KeyRepeat -int 1
defaults write NSGlobalDomain InitialKeyRepeat -int 15

# Disable press and hold for KeyRepeat
defaults write -g ApplePressAndHoldEnabled -bool false
defaults delete -g ApplePressAndHoldEnabled

# Disable automatic capitalization
defaults write NSGlobalDomain NSAutomaticCapitalizationEnabled -bool false

# Disable automatic period substitution
defaults write NSGlobalDomain NSAutomaticPeriodSubstitutionEnabled -bool false

# Disable smart quotes
defaults write NSGlobalDomain NSAutomaticQuoteSubstitutionEnabled -bool false

# Disable smart dashes
defaults write NSGlobalDomain NSAutomaticDashSubstitutionEnabled -bool false

# Enable full keyboard access for all controls
defaults write NSGlobalDomain AppleKeyboardUIMode -int 3

echo "✅ Keyboard and text input configuration complete"
echo ""

# ==============================================================================
# SAVE DIALOGS
# ==============================================================================

echo "💾 Configuring save dialogs..."

# Always expand save panel by default
defaults write NSGlobalDomain NSNavPanelExpandedStateForSaveMode -bool true
defaults write NSGlobalDomain NSNavPanelExpandedStateForSaveMode2 -bool true

# Save to disk (not iCloud) by default
# defaults write NSGlobalDomain NSDocumentSaveNewDocumentsToCloud -bool false

echo "✅ Save dialogs configuration complete"
echo ""

# ==============================================================================
# DOCK SETTINGS
# ==============================================================================

echo "🏠 Configuring Dock settings..."

# Auto-hide Dock
defaults write com.apple.dock autohide -bool true

# Disable "click wallpaper to show desktop"
defaults write com.apple.dock showDesktop -bool false

# Change minimize/maximize window effect
defaults write com.apple.dock mineffect -string "scale"

# Minimize windows into their application's icon
defaults write com.apple.dock minimize-to-application -bool true

# Show indicator lights for open applications in the Dock
defaults write com.apple.dock show-process-indicators -bool true

# Show only open applications in the Dock
defaults write com.apple.dock static-only -bool true

# Don't animate opening applications from the Dock
defaults write com.apple.dock launchanim -bool false

# Don't show recently used applications in Dock
defaults write com.apple.dock show-recents -bool false

# Speed up Mission Control animations
defaults write com.apple.dock expose-animation-duration -float 0.1

# Don't automatically rearrange Spaces based on most recent use
defaults write com.apple.dock mru-spaces -bool false

# Make Dock icons smaller (36 pixels) - uncomment if desired
# defaults write com.apple.dock tilesize -int 36

# Remove the auto-hiding Dock delay - uncomment if desired
# defaults write com.apple.dock autohide-delay -float 0

# Wipe all (default) app icons from the Dock - uncomment if desired
# This is only really useful when setting up a new Mac
# defaults write com.apple.dock persistent-apps -array

echo "✅ Dock configuration complete"
echo ""

# ==============================================================================
# HOT CORNERS
# ==============================================================================

echo "🖱️  Configuring hot corners..."

# Hot corners configuration
# Possible values:
#  0: no-op
#  2: Mission Control
#  3: Show application windows
#  4: Desktop
#  5: Start screen saver
#  6: Disable screen saver
#  7: Dashboard
# 10: Put display to sleep
# 11: Launchpad
# 12: Notification Center
# 13: Lock Screen

# Top left screen corner → Mission Control (uncomment if desired)
# defaults write com.apple.dock wvous-tl-corner -int 2
# defaults write com.apple.dock wvous-tl-modifier -int 0

# Top right screen corner → Disabled
defaults write com.apple.dock wvous-tr-corner -int 0
defaults write com.apple.dock wvous-tr-modifier -int 0

echo "✅ Hot corners configuration complete"
echo ""

# ==============================================================================
# TERMINAL SETTINGS
# ==============================================================================

echo "💻 Configuring Terminal settings..."

# Use UTF-8 encoding in Terminal
defaults write com.apple.terminal StringEncodings -array 4

echo "✅ Terminal configuration complete"
echo ""

# ==============================================================================
# SYSTEM UI SETTINGS
# ==============================================================================

echo "🎛️  Configuring system UI settings..."

# Show battery percentage in menu bar
defaults -currentHost write com.apple.controlcenter.plist BatteryShowPercentage -bool true

# Show volume icon in menu bar
defaults write com.apple.controlcenter.plist Sound -int 18

# Use 24-hour time format
defaults write NSGlobalDomain AppleICUForce24HourTime -bool true

# Reduce status item spacing
defaults -currentHost write -globalDomain NSStatusItemSpacing -int 12
defaults -currentHost write -globalDomain NSStatusItemSelectionPadding -int 12

echo "✅ System UI configuration complete"
echo ""

# ==============================================================================
# SCREENSHOT SETTINGS
# ==============================================================================

echo "📸 Configuring screenshot settings..."

# Create Screenshots directory
mkdir -p ~/Pictures/Screenshots

# Save screenshots to Screenshots folder
defaults write com.apple.screencapture location -string "${HOME}/Pictures/Screenshots"

# Save screenshots in PNG format
defaults write com.apple.screencapture type -string "png"

# Disable shadow in screenshots
defaults write com.apple.screencapture disable-shadow -bool true

echo "✅ Screenshot configuration complete"
echo ""

# ==============================================================================
# SECURITY SETTINGS
# ==============================================================================

echo "🔒 Configuring security settings..."

# Require password immediately after sleep or screen saver
defaults write com.apple.screensaver askForPassword -int 1
defaults write com.apple.screensaver askForPasswordDelay -int 0

echo "✅ Security configuration complete"
echo ""

# ==============================================================================
# PERFORMANCE SETTINGS
# ==============================================================================

echo "⚡ Configuring performance settings..."

# Disable automatic termination of inactive apps
defaults write NSGlobalDomain NSDisableAutomaticTermination -bool true

echo "✅ Performance configuration complete"
echo ""

# ==============================================================================
# SAFARI & WEBKIT SETTINGS
# ==============================================================================

echo "🌐 Configuring Safari and WebKit settings..."

# Privacy: don't send search queries to Apple
defaults write com.apple.Safari UniversalSearchEnabled -bool false
defaults write com.apple.Safari SuppressSearchSuggestions -bool true

# Show the full URL in the address bar
defaults write com.apple.Safari ShowFullURLInSmartSearchField -bool true

# Enable Debug Menu in Safari
defaults write com.apple.Safari IncludeInternalDebugMenu -bool true

# Enable the Develop menu and Web Inspector in Safari
defaults write com.apple.Safari IncludeDevelopMenu -bool true
defaults write com.apple.Safari WebKitDeveloperExtrasEnabledPreferenceKey -bool true
defaults write com.apple.Safari com.apple.Safari.ContentPageGroupIdentifier.WebKit2DeveloperExtrasEnabled -bool true

# Add Web Inspector context menu
defaults write NSGlobalDomain WebKitDeveloperExtras -bool true

# Warn about fraudulent websites
defaults write com.apple.Safari WarnAboutFraudulentWebsites -bool true

# Update extensions automatically
defaults write com.apple.Safari InstallExtensionUpdatesAutomatically -bool true

echo "✅ Safari and WebKit configuration complete"
echo ""

# ==============================================================================
# TEXTEDIT SETTINGS
# ==============================================================================

echo "📝 Configuring TextEdit settings..."

# Use plain text mode for new TextEdit documents
defaults write com.apple.TextEdit RichText -int 0

# Use UTF-8 in TextEdit
defaults write com.apple.TextEdit PlainTextEncoding -int 4
defaults write com.apple.TextEdit PlainTextEncodingForWrite -int 4

echo "✅ TextEdit configuration complete"
echo ""

# ==============================================================================
# ACTIVITY MONITOR SETTINGS
# ==============================================================================

echo "📊 Configuring Activity Monitor settings..."

# Show all processes in Activity Monitor
defaults write com.apple.ActivityMonitor ShowCategory -int 0

# Sort Activity Monitor by CPU usage
defaults write com.apple.ActivityMonitor SortColumn -string "CPUUsage"
defaults write com.apple.ActivityMonitor SortDirection -int 0

echo "✅ Activity Monitor configuration complete"
echo ""

# ==============================================================================
# APP STORE SETTINGS
# ==============================================================================

echo "🛍️  Configuring App Store settings..."

# Disable App Store automatic downloads
defaults write com.apple.SoftwareUpdate AutomaticDownload -bool false

echo "✅ App Store configuration complete"
echo ""

# ==============================================================================
# APPLY CHANGES
# ==============================================================================

echo "🔄 Applying changes..."
echo "   Restarting affected applications..."

# Restart affected apps to apply changes
killall Finder
killall Dock
killall SystemUIServer

echo "✅ Changes applied successfully"
echo ""

# ==============================================================================
# COMPLETION
# ==============================================================================

echo "🎉 macOS system configuration complete!"