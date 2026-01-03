function dotsup
    cd ~/.mac-dots
    git add .
    git commit -m "Update dotfiles"
    git push origin
    echo "Dotfiles updated and pushed"
end