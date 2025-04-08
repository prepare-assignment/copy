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