---
parent: Installation
nav_order: 10
---

# Installing forge
{: .no_toc }

- TOC
{:toc}

## Python version

forge currently works with python 3.9-3.12.

## Install git

Make sure you have git installed.
Here are
[instructions for installing git in various environments](https://github.com/git-guides/install-git).

## Get your API key

To work with OpenAI's models like GPT-4o or GPT-3.5 you need a paid
[OpenAI API key](https://help.openai.com/en/articles/4936850-where-do-i-find-my-secret-api-key).
Note that this is different than being a "ChatGPT Plus" subscriber.

To work with Anthropic's models like Claude 3.5 Sonnet you need a paid
[Anthropic API key](https://docs.anthropic.com/claude/reference/getting-started-with-the-api).


{% include venv-pipx.md %}

## Mac/Linux install

```
# Install forge
python -m pip install -U --upgrade-strategy only-if-needed forge-chat

# To work with GPT-4o:
$ forge --4o --openai-api-key sk-xxx...

# To work with Claude 3.5 Sonnet:
$ forge --sonnet --anthropic-api-key sk-xxx...
```

## Windows install

```
# Install forge
python -m pip install -U --upgrade-strategy only-if-needed forge-chat

# To work with GPT-4o:
$ forge --4o --openai-api-key sk-xxx...

# To work with Claude 3.5 Sonnet:
$ forge --sonnet --anthropic-api-key sk-xxx...
```

{% include python-m-forge.md %}

## Working with other LLMs

{% include works-best.md %}

## You are done!

There are some [optional install steps](/docs/install/optional.html) you could consider.
See the [usage instructions](https://forge.chat/docs/usage.html) to start coding with forge.

