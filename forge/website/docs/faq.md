---
nav_order: 90
description: Frequently asked questions about forge.
---

# FAQ
{: .no_toc }

- TOC
{:toc}

{% include help-tip.md %}

## How can I add ALL the files to the chat?

People regularly ask about how to add **many or all of their repo's files** to the chat.
This is probably not a good idea and will likely do more harm than good.

The best approach is think about which files need to be changed to accomplish
the task you are working on. Just add those files to the chat.

Usually when people want to add "all the files" it's because they think it
will give the LLM helpful context about the overall code base.
forge will automatically give the LLM a bunch of additional context about
the rest of your git repo.
It does this by analyzing your entire codebase in light of the
current chat to build a compact
[repository map](https://forge.chat/2023/10/22/repomap.html).

Adding a bunch of files that are mostly irrelevant to the
task at hand will often distract or confuse the LLM.
The LLM will give worse coding results, and sometimese even fail to correctly edit files.
Addings extra files will also increase your token costs.

Again, it's usually best to just add the files to the chat that will need to be modified.
If you still wish to add lots of files to the chat, you can:

- Use a wildcard when you launch forge: `forge src/*.py`
- Use a wildcard with the in-chat `/add` command: `/add src/*.py`
- Give the `/add` command a directory name and it will recursively add every file under that dir: `/add src`

## Can I use forge in a large (mono) repo?

forge will work in any size repo, but is not optimized for quick
performance and response time in very large repos.
There are some things you can do to improve performance.

Be sure to check the
[general usage tips](/docs/usage/tips.html)
before considering this large-repo specific advice.
To get the best results from forge you want to 
be thoughtful about how you add files to the chat,
regardless of your repo size.

You can change into a sub directory of your repo that contains the
code you want to work on and use the `--subtree-only` switch.
This will tell forge to ignore the repo outside of the
directory you start in.

You can also create a `.forgeignore` file to tell forge
to ignore parts of the repo that aren't relevant to your task.
This file conforms to `.gitignore` syntax and conventions.

You can use `--forgeignore <filename>` to name a specific file
to use for ignore patterns.
You might have a few of these handy for when you want to work on
frontend, backend, etc portions of your repo.

## Can I use forge with multiple git repos at once?

Currently forge can only work with one repo at a time.

There are some things you can try if you need to work with
multiple interrelated repos:

- You can run forge in repo-A where you need to make a change
and use `/read` to add some files read-only from another repo-B.
This can let forge see key functions or docs from the other repo.
- You can run `forge --show-repo-map > map.md` within each
repo to create repo maps.
You could then run forge in repo-A and 
use `/read ../path/to/repo-B/map.md` to share
a high level map of the other repo.
- You can use forge to write documentation about a repo.
Inside each repo, you could run `forge docs.md`
and work with forge to write some markdown docs.
Then while using forge to edit repo-A
you can `/read ../path/to/repo-B/docs.md` to
read in those docs from the other repo.
- In repo A, ask forge to write a small script that demonstrates
the functionality you want to use in repo B.
Then when you're using forge in repo B, you can 
`/read` in that script.

## How do I turn on the repository map?

Depending on the LLM you are using, forge may launch with the repo map disabled by default:

```
Repo-map: disabled
```

This is because weaker models get easily overwhelmed and confused by the content of the
repo map. They sometimes mistakenly try to edit the code in the repo map.
The repo map is usually disabled for a good reason.

If you would like to force it on, you can run forge with `--map-tokens 1024`.

## How do I include the git history in the context?

When starting a fresh forge session, you can include recent git history in the chat context. This can be useful for providing the LLM with information about recent changes. To do this:

1. Use the `/run` command with `git diff` to show recent changes:
   ```
   /run git diff HEAD~1
   ```
   This will include the diff of the last commit in the chat history.

2. To include diffs from multiple commits, increase the number after the tilde:
   ```
   /run git diff HEAD~3
   ```
   This will show changes from the last three commits.

Remember, the chat history already includes recent changes made during the current session, so this tip is most useful when starting a new forge session and you want to provide context about recent work.

{: .tip }
The `/git` command will not work for this purpose, as its output is not included in the chat. 

## How can I run forge locally from source code?

To run the project locally, follow these steps:

```
# Clone the repository
git clone git@github.com:forge-AI/forge.git

# Navigate to the project directory
cd forge

# It's recommended to make a virtual environment

# Install forge in editable/development mode, 
# so it runs from the latest copy of these source files
python -m pip install -e .

# Run the local version of forge
python -m forge
```



## Can I change the system prompts that forge uses?

forge is set up to support different system prompts and edit formats
in a modular way. If you look in the `forge/coders` subdirectory, you'll
see there's a base coder with base prompts, and then there are
a number of
different specific coder implementations.

If you're thinking about experimenting with system prompts
this document about
[benchmarking GPT-3.5 and GPT-4 on code editing](https://forge.chat/docs/benchmarks.html)
might be useful background.

While it's not well documented how to add new coder subsystems, you may be able
to modify an existing implementation or use it as a template to add another.

To get started, try looking at and modifying these files.

The wholefile coder is currently used by GPT-3.5 by default. You can manually select it with `--edit-format whole`.

- wholefile_coder.py
- wholefile_prompts.py

The editblock coder is currently used by GPT-4o by default. You can manually select it with `--edit-format diff`.

- editblock_coder.py
- editblock_prompts.py

The universal diff coder is currently used by GPT-4 Turbo by default. You can manually select it with `--edit-format udiff`.

- udiff_coder.py
- udiff_prompts.py

When experimenting with coder backends, it helps to run forge with `--verbose --no-pretty` so you can see
all the raw information being sent to/from the LLM in the conversation.

You can also refer to the
[instructions for installing a development version of forge](https://forge.chat/docs/install/optional.html#install-the-development-version-of-forge).


## How are the "forge wrote xx% of code" stats computed?

[forge is tightly integrated with git](/docs/git.html) so all
one of forge's code changes are committed to the repo with proper attribution.
The 
[stats are computed](https://github.com/forge-AI/forge/blob/main/scripts/blame.py)
by doing something like `git blame` on the repo,
and counting up who wrote all the new lines of code in each release.
Only lines in source code files are counted, not documentation or prompt files.

## Can I share my forge chat transcript?

Yes, you can now share forge chat logs in a pretty way.

1. Copy the markdown logs you want to share from `.forge.chat.history.md` and make a github gist. Or publish the raw markdown logs on the web any way you'd like.

   ```
   https://gist.github.com/forge-AI/2087ab8b64034a078c0a209440ac8be0
   ```

2. Take the gist URL and append it to:

   ```
   https://forge.chat/share/?mdurl=
   ```

This will give you a URL like this, which shows the chat history like you'd see in a terminal:

```
https://forge.chat/share/?mdurl=https://gist.github.com/forge-AI/2087ab8b64034a078c0a209440ac8be0
```

## Can I edit files myself while forge is running?

Yes. forge always reads the latest copy of files from the file
system when you send each message.

While you're waiting for forge's reply to complete, it's probably unwise to
edit files that you've added to the chat.
Your edits and forge's edits might conflict.

## What is forge AI LLC?

forge AI LLC is the company behind the forge AI coding tool.
forge is 
[open source and available on GitHub](https://github.com/forge-AI/forge)
under an 
[Apache 2.0 license](https://github.com/forge-AI/forge/blob/main/LICENSE.txt).


<div style="height:80vh"></div>

