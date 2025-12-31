# Fish Shell Plugin Keybinding Conflicts

## Problem Overview

When multiple Fish shell plugins try to bind the same key (like Tab, Ctrl+R, etc.), the **last plugin to bind wins**. This commonly happens when:

1. Plugins use event handlers (`--on-variable fish_key_bindings`)
2. Fish version upgrades trigger key binding changes
3. Multiple plugins want to control the same key

## Common Symptoms

- Tab completion suddenly stops working after updating Fish
- Expected plugin keybinding doesn't trigger
- Running `bind | grep <key>` shows wrong function bound to your key
- Other plugins' features mysteriously stop working

## Root Cause: Event Handler Execution Order

Fish plugins often use `--on-variable fish_key_bindings` event handlers to set up keybindings. These handlers run:

1. **After all conf.d files load** (not during)
2. **Whenever `fish_key_bindings` variable changes**
3. **In unpredictable order** (based on when functions are defined)

### Example Conflict

```fish
# Plugin A (autopair.fish)
function _autopair_fish_key_bindings --on-variable fish_key_bindings
    bind --mode insert \t _autopair_tab  # Binds Tab to autopair
end

# Plugin B (fifc)
# Binds Tab in conf.d/fifc.fish
bind --mode insert \t _fifc  # This gets overridden!
```

**Result:** Autopair's event handler runs after fifc's initial binding, overriding Tab → `_fifc` with Tab → `_autopair_tab`.

## The Fix Pattern

Add an event handler to the plugin you want to "win" the keybinding conflict:

```fish
# In your plugin's conf.d file (e.g., conf.d/fifc.fish)

# Initial binding
bind --mode insert \t _fifc
bind --mode insert $fifc_keybinding _fifc

# Event handler to persist binding
function _fifc_rebind_tab --on-variable fish_key_bindings
    # Only rebind if in interactive mode
    status is-interactive || return

    # Rebind your key(s) whenever fish_key_bindings changes
    bind --mode insert \t _fifc
    bind --mode insert $fifc_keybinding _fifc
end
```

### Why This Works

1. **Runs on every keybinding change**: Whenever any plugin modifies `fish_key_bindings`, your handler re-applies your bindings
2. **Execution order doesn't matter**: Even if other plugins override your binding, your handler runs after and reclaims it
3. **Non-invasive**: Doesn't require modifying other plugins

## Real-World Example: fifc + autopair.fish

**Conflict:** Both plugins wanted to control Tab key
- `autopair.fish`: Tab → `_autopair_tab` (for smart pair completion)
- `fifc`: Tab → `_fifc` (for fzf fuzzy completion)

**Solution Applied:**

Added to `/Users/devadathanmb/.config/fish/conf.d/fifc.fish`:

```fish
# Ensure fifc tab binding persists even when other plugins rebind keys
function _fifc_rebind_tab --on-variable fish_key_bindings
    status is-interactive || return

    for mode in default insert
        bind --mode $mode \t _fifc
        bind --mode $mode $fifc_keybinding _fifc
    end
end
```

**Result:** Both plugins coexist! autopair still handles pair completion, fifc controls Tab.

## Diagnostic Commands

### 1. Check Current Bindings
```fish
# Check what Tab is bound to
bind | grep -E "(\\t|tab)"

# Check specific mode
bind -M insert | grep "\t"

# Check all bindings for a specific function
bind | grep "_fifc"
```

### 2. Find Conflicting Plugins
```fish
# List all functions with event handlers
functions -a | grep "on-variable fish_key_bindings"

# Check specific plugin's event handlers
functions --details _autopair_fish_key_bindings
```

### 3. Test Binding Override
```fish
# Manually rebind and test
bind -M insert \t _fifc
# Then press Tab to see if it works
```

## When to Use This Pattern

### ✅ Use when:
- You have a preferred plugin that should control a specific key
- Two plugins conflict and you can't/won't remove either
- Plugin updates break your keybindings
- You want deterministic binding behavior

### ❌ Don't use when:
- You can simply remove one conflicting plugin
- You can reconfigure a plugin to use different keys
- The conflict is with Fish's built-in bindings (use `bind --preset` instead)

## Alternative Solutions

### 1. Reconfigure Plugin Keybindings

Some plugins let you choose different keys:

```fish
# Example: Change fifc to use Ctrl+Space instead of Tab
set -U fifc_keybinding \cx  # Ctrl+X
```

### 2. Disable Unwanted Event Handlers

If you don't need a plugin's event handler:

```fish
# In your config.fish
function _autopair_fish_key_bindings --on-variable fish_key_bindings
    # Disabled - do nothing
end
```

### 3. Load Order Hacks (Not Recommended)

Renaming conf.d files to control load order (e.g., `00-fifc.fish`, `99-autopair.fish`) **does NOT work** for event handlers since they run after all conf.d files load.

## Fish Version Considerations

### Fish 4.3+ Key Binding Migration

Fish 4.3 introduced a migration for `fish_key_bindings`:
- Moved from **universal** scope to **global** scope
- Creates `conf.d/fish_frozen_key_bindings.fish` on upgrade
- **Triggers all `--on-variable fish_key_bindings` handlers**

This migration is why keybinding conflicts suddenly appear after upgrading to Fish 4.3+.

### Generated Migration File

If you see `conf.d/fish_frozen_key_bindings.fish`:

```fish
# This file was created by fish when upgrading to version 4.3
set --global fish_key_bindings fish_vi_key_bindings
set --erase --universal fish_key_bindings
```

This file is safe to keep and ensures consistent key bindings across Fish versions.

## Debugging Checklist

When keybindings stop working:

1. ✅ Check binding: `bind -M insert | grep <your-key>`
2. ✅ Check function exists: `functions --query <your-function> && echo "exists"`
3. ✅ Check plugin loaded: `ls ~/.config/fish/conf.d/ | grep <plugin>`
4. ✅ Check for event handlers: `functions -a | grep "on-variable"`
5. ✅ Test in fresh shell: `exec fish`
6. ✅ Test manual binding: `bind -M insert <key> <function>`

## Related Resources

- [Fish Shell bind documentation](https://fishshell.com/docs/current/cmds/bind.html)
- [Fish Shell event handlers](https://fishshell.com/docs/current/language.html#event-handlers)
- [Understanding Fish plugin load order](https://fishshell.com/docs/current/index.html#configuration-files)

## Example: Creating Your Own Protected Binding

```fish
# In ~/.config/fish/conf.d/my-bindings.fish

if status is-interactive
    # Define your custom function
    function my_custom_command
        echo "My custom command!"
        commandline -f repaint
    end

    # Initial binding
    bind --mode insert \cg my_custom_command  # Ctrl+G

    # Protect it with an event handler
    function _my_rebind --on-variable fish_key_bindings
        status is-interactive || return
        bind --mode insert \cg my_custom_command
    end
end
```

Now Ctrl+G will always trigger `my_custom_command`, even if other plugins try to override it!

---

**Last Updated:** 2025-12-31
**Fish Version:** 4.3.2
**Issue:** Tab completion conflict between fifc and autopair.fish
