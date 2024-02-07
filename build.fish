#!/opt/homebrew/bin/fish

if ! command -q rsync
    brew install rsync
end

if ! command -q rg
    brew install ripgrep
end

if ! command -q sd
    brew install sd
end

if ! command -q cargo
    brew install rust
end

if ! command -q node
    brew install node
    npm install -g npm@latest
end

if ! command -q bun
    brew install "oven-sh/bun/bun"
end

if ! command -q ~/.bun/bin/cleancss
    bun install -g clean-css clean-css-cli terser rollup
end

if ! command -q minhtml
    cargo install --all-features minhtml
end

set -xl current_dir (pwd);

/bin/rm -rf "$current_dir/docs";

/usr/bin/rsync --quiet -av --exclude="docs" --exclude=".git" --exclude="material" --exclude=".gitignore" --exclude="build.fish" --exclude=".vscode" --exclude="**.DS_Store" "$current_dir/" "$current_dir/docs"

for cssFile in (find ./docs -name "**.css")
    cleancss "$cssFile" -o "$cssFile"
end

for htmlFile in (find ./docs -name "**.html")
    minhtml --keep-closing-tags --ensure-spec-compliant-unquoted-attribute-values --remove-bangs --remove-processing-instructions --keep-html-and-head-opening-tags --minify-js --do-not-minify-doctype --minify-css "$htmlFile" -o "$htmlFile"
end

for cssFile in (find ./docs -name "**.css")
    set -xl sriName '{{sri-'(basename -s .css "$cssFile")'.css}}'
    set -xl sriHash (shasum -b -a 512 "$cssFile" | awk '{ print $1 }' | xxd -r -p | base64)
    echo "$sriHash"
    /opt/homebrew/bin/sd -F "$sriName" "$sriHash" (find ./docs -name "**.html")
end
