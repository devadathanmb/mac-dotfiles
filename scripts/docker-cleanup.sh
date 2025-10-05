#!/bin/bash
# docker-deep-clean.sh - Complete Docker cleanup

echo "🧹 Docker Deep Cleanup Script"
echo "=============================="

# Show what will be removed
echo ""
echo "This will remove:"
echo "  • Stopped containers"
echo "  • Unused networks"
echo "  • Dangling images"
echo "  • Unused images"
echo "  • Build cache"
echo ""

read -p "Continue? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

# Show current usage
echo ""
echo "📊 Before cleanup:"
docker system df

# Remove everything unused
echo ""
echo "🗑️  Cleaning up..."
docker system prune -a -f --volumes

# Show space saved
echo ""
echo "✅ Cleanup complete!"
echo "📊 After cleanup:"
docker system df
