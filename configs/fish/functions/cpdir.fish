function cpdir
    set source_dir $argv[1]
    set target_dirs $argv[2..-1]

    if test -z "$source_dir" -o (count $target_dirs) -eq 0
        echo "Usage: make_dirs_and_copy_files <source_dir> <target_dir1> <target_dir2> ..."
        return 1
    end

    if not test -d "$source_dir"
        echo "Source directory does not exist: $source_dir"
        return 1
    end

    for target_dir in $target_dirs
        if test -d "$target_dir"
            echo "Target directory already exists: $target_dir"
            continue
        end
        mkdir -p "$target_dir" && echo "Created directory: $target_dir"
        cp -r "$source_dir"/* "$target_dir" && echo "Copied files from $source_dir to $target_dir"
    end
end
