function dotsup
    set -l dots_repo $HOME/.mac-dots
    if set -q DOTFILES_REPO
        set dots_repo $DOTFILES_REPO
    end
    cd $dots_repo
    git add .
    git commit -m "Update dotfiles"
    git push origin
    echo "Dotfiles updated and pushed"
end
