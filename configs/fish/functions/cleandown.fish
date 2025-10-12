function cleandown
    set downloads_dir $HOME/Downloads
    set trash_dir /tmp/trash

    mkdir -p $trash_dir
    find $downloads_dir -maxdepth 1 -type f \( -iname "*.pdf" -o -iname "*.csv" -o -iname "*.zip" -o -iname "*.xlsx" \) -exec mv -f {} $trash_dir \; 2>/dev/null
    echo "Moved files from $downloads_dir to $trash_dir"
end
