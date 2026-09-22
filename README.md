# Copy actions

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
  description: "File/directory to prepare_copy (glob)"
  required: true
destination:
  description: "Destination to prepare_copy to"
  required: true
force:
  description: "Force the prepare_copy (overwrite)"
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
preserve-path:
  description: "Preserve directory structure after common path"
  type: boolean
  default: false
```

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
