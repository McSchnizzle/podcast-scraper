#!/bin/bash
# Fix Python MallocStackLogging warnings on macOS
# Adds MallocStackLogging=0 to .zshrc to suppress malloc debugging messages

ZSHRC="$HOME/.zshrc"
MALLOC_SETTING="export MallocStackLogging=0"
LAUNCHCTL_SETTING="launchctl setenv MallocStackLogging 0"

echo "🔧 Fixing Python MallocStackLogging warnings..."

# Check if the setting already exists
if grep -q "MallocStackLogging" "$ZSHRC"; then
    echo "⚠️  MallocStackLogging setting already exists in .zshrc"
    echo "Current setting:"
    grep "MallocStackLogging" "$ZSHRC"
    
    read -p "Do you want to replace it? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Remove existing lines with MallocStackLogging
        sed -i.bak '/MallocStackLogging/d' "$ZSHRC"
        echo "✅ Removed existing MallocStackLogging settings"
    else
        echo "❌ Skipping - no changes made"
        exit 0
    fi
fi

# Add the new setting
echo "" >> "$ZSHRC"
echo "# Fix malloc stack logging warnings for all processes" >> "$ZSHRC"
echo "$MALLOC_SETTING" >> "$ZSHRC"

# Set for current macOS session (affects all processes including Claude Code)
echo "🔧 Setting environment variable for current session..."
eval "$LAUNCHCTL_SETTING"

echo "✅ Added MallocStackLogging=0 to .zshrc"
echo "✅ Set MallocStackLogging=0 for current macOS session"
echo "🔄 Please restart your terminal or run: source ~/.zshrc"
echo ""
echo "This will suppress the annoying malloc debugging messages:"
echo "Python(XXXXX) MallocStackLogging: can't turn off malloc stack logging because it was not enabled."