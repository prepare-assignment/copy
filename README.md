# Copy

Copy files/directories. The action is modeled after linux `cp` command. For more information see the [man page](https://man7.org/linux/man-pages/man1/cp.1.html).

## Example

Copy all SVG image to output directory

```yaml
- name: Copy images
  uses: copy
  with:
    source: "images/*.svg"
    destination: "out/images"
```

## Options

The following options are available:

```yaml
source:
  description: "Files/directories to copy (glob)"
  required: true
destination:
  description: "Destination to copy to"
  required: true
force:
  description: "Overwrite existing files"
  type: boolean
  default: true
recursive:
  description: "Allow copy of directories"
  type: boolean
  default: true
allow-outside-working-directory:
  description: "Destination/matched files can be outside the working directory"
  type: boolean
  default: false
fail-no-match:
  description: "Fail if the glob doesn't match anything, otherwise only log a warning"
  type: boolean
  default: true
preserve-path:
  description: "Preserve directory structure after common path"
  type: boolean
  default: false
include-hidden:
  description: "Also match hidden files and directories (starting with a '.') with wildcards such as '*' and '**'"
  type: boolean
  default: false
```

## How files and directories are copied

- A **file** is copied into the destination if it's an existing directory, otherwise to the destination itself (e.g. to rename it).
- If the glob matches **several files**, the destination must be an existing directory (except with `preserve-path`).
- A **directory** (needs `recursive`) is copied into the destination if it's an existing directory (`in` → `out/in`), or as the destination if it doesn't exist yet, like `cp -r` (`in` → `new-dir`).
- Without `force`, the task fails if a file (also one inside a copied directory) would be overwritten.
- Everything is checked before anything is copied, so a failing task doesn't leave half of the files copied.

### preserve-path

With `preserve-path`, the directory structure after the part the source and destination have in common is kept, and the destination directory is created if needed:

```yaml
- name: Copy resources
  uses: copy
  with:
    source: "solution/src/main/resources/**/*.*"
    destination: out/assignment/src/main/resources
    preserve-path: true
```

`solution/src/main/resources/images/logo.png` is copied to `out/assignment/src/main/resources/images/logo.png`. The common part is the longest sequence of directories at the end of the destination that also occurs in the source (`src/main/resources`).

## Outputs

The following output are available:

```yaml
copied:
  description: The new path(s)
  type: array
  items: string
```

Where `copied` is the new path(s) of the copied files/directories.

> :warning: If a directory is copied, it will only list the new directory path, not all sub files/directories.

## Releases

Releases are automated with [semantic-release](https://semantic-release.gitbook.io/). Pull requests are squash merged, so the PR title becomes the commit on `main` and must follow [Conventional Commits](https://www.conventionalcommits.org/) (checked on every PR):

| PR title | Release |
|----------|---------|
| `fix: ...`, `perf: ...` | patch (1.2.3 → 1.2.4) |
| `feat: ...` | minor (1.2.3 → 1.3.0) |
| `!` after the type (e.g. `feat!: ...`, `refactor!: ...`) or a `BREAKING CHANGE:` footer | major (1.2.3 → 2.0.0) |
| `docs:`, `chore:`, `ci:`, `build:`, `refactor:`, `test:`, `style:`, `revert:` | no release |

On every merge to `main` the next version is determined, tagged (`vX.Y.Z`) and a GitHub release is created. The major tag (e.g. `v1`) is moved to the new release, so `uses: copy@v1` always gets the newest 1.x version.

Because the major tag moves, `git pull` in an existing clone can fail with `! [rejected] v1 -> v1 (would clobber existing tag)`. Update the tags once with `git fetch --tags --force` and pull again.
