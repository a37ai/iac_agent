---
parent: Installation
nav_order: 100
---

# Install with pipx

If you are using forge to work on a python project, sometimes your project will require
specific versions of python packages which conflict with the versions that forge
requires.
If this happens, the `python -m pip install` command may return errors like these:

```
forge-chat 0.23.0 requires somepackage==X.Y.Z, but you have somepackage U.W.V which is incompatible.
```

You can avoid this problem by installing forge using `pipx`,
which will install it globally on your system
within its own python environment.
This way you can use forge to work on any python project,
even if that project has conflicting dependencies.

Install [pipx](https://pipx.pypa.io/stable/) then just do:

```
pipx install forge-chat
```


## pipx on replit

{% include replit-pipx.md %}

