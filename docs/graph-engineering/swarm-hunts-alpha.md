---
title: "How to Build a Swarm of AI Agents That Hunts Alpha 24/7"
source: "https://x.com/RohOnChain/status/2074134246784921977"
author:
  - "[[@RohOnChain]]"
published: 2026-07-06
created: 2026-07-24
description: "I will break down how to build the swarm of AI agents that replaces an entire quant research team.Let's get straight to it.> Bookmark This -I'm Roan, ..."
coverImage: https://pbs.twimg.com/media/HMYFvP3aEAAgG9R?format=jpg&name=large
tags:
  - "clippings"
---

How to Build a Swarm of AI Agents That Hunts Alpha 24/7

I will break down how to build the swarm of AI agents that replaces an entire quant research team.

Let's get straight to it.
> Bookmark This -
I'm Roan, a backend developer working on system design, HFT-style execution, and quantitative trading systems. My work focuses on how prediction markets actually behave under load. For any suggestions, thoughtful collaborations, partnerships DMs are open.
In my last article I said I would personally walk through the first 20 setups of anyone building an AI quant system.I meant it.
Four builders are already deep in the process with me. One of them is running the full self-improving hedge fund loop as we speak.
The offer is still open.
If you are building an alpha research system, about to start, or even just thinking about it, reply under this article or DM me your current setup. I will personally walk through your architecture and show you the gap between what you have and a swarm that hunts alpha on its own.
If I do not reply, you were not in the first 20. Move fast.
Most quants still hunt alpha the same way they did a decade ago.
They read a paper. They open a Jupyter notebook. They engineer a few features. They run a backtest. They squint at the Sharpe ratio. They move on to the next idea.
They are the pipeline.
Every stage of the research is them, sitting at a screen, running one hypothesis at a time.
The smartest quant builders on the planet have stopped doing that.
They build swarms. Each agent in the swarm owns one stage of the research. The agents work in parallel. The swarm runs continuously. New alpha appears every morning while they sleep.
Boris Cherny, the head of Claude Code at Anthropic, said it two weeks ago. "I don't prompt Claude anymore. I have loops running that prompt Claude and figuring out what to do. My job is to write loops."
That single sentence reframed how every serious builder on earth thinks about AI.
For quant research it changes everything.
Because alpha research is already a pipeline. Read the paper. Extract the hypothesis. Engineer the features. Backtest across 20 years of data. Check the significance. Check whether the signal survives across regimes. Decompose against every known factor.
Every serious fund on Wall Street runs that exact pipeline. Renaissance runs it with 100 PhDs. Two Sigma runs it with 200. Citadel runs it with more.
The only difference is they need hundreds of humans sitting inside the pipeline. You do not.
> A swarm of AI agents can run every stage of that pipeline for you. Each agent specialized. Each agent running on the model that fits its complexity. All of them running 24/7 in parallel.
I have been building this swarm for the last few days.
It reads new research papers overnight. It studies the math inside them. It extracts the exact hypothesis being claimed. It engineers the required features. It backtests the signal against 20 years of history. It runs the statistical rigor. It checks for overfitting. It flags anything that only works in one market regime.
By the end of this article you will know the exact architecture of a six-agent alpha research swarm.
You will know the tool that lets you build it in a weekend without writing your own agent framework from scratch.
And you will know the five failure modes that kill 90 percent of retail attempts.
Let's get into it.
Part 1: What a Swarm Actually Is
> A prompt is a question. You ask, the model answers once, and it stops.
> A loop is a job. The agent keeps working, checks its own progress, and keeps going until the task is actually finished.
> A swarm is many loops running in parallel. Each loop is a specialist. Each specialist owns one stage of the pipeline. The output of one feeds the input of the next.
That is the entire mental model.
If you have used Claude Code, Cursor, or Codex, you have used a loop without knowing it. The agent calls a model, the model picks an action, the action runs, the result goes back to the model, and it repeats until the goal is met.
The loop is what makes an agent an agent instead of a single answer.
A swarm is what makes a research team a research team instead of one researcher typing.
Part 2: The Tool That Runs The Swarm
You could try to build this yourself with Python scripts that shell out to different APIs.
I tried. It breaks the moment one agent needs to wait on another. It breaks the moment you need state to persist across cycles. It breaks the moment you want to run six loops in parallel on different models.
You end up building your own agent framework from scratch instead of doing research.
Then I found Slate.

Slate is an AI coding harness built by @wearerandomlabs ([x.com/wearerandomlabs](https://x.com/wearerandomlabs)). It runs in your terminal. It fans out any task into a swarm of subagents across your codebase. It picks any model you want on any step. Your existing subscription works.
The reason I use it for this swarm is a capability they just launched called Programs.
A Program is a loop written in JavaScript that Slate runs for you.
A prompt runs once and stops. A Program is an engineered loop. It runs continuously. It holds state between runs. It keeps going until the task is done.
You decide what happens on each step. Which model handles which step. What the loop checks before it continues. When it stops.
You do not write the Program alone. You tell Slate what you want and it drafts the loop with you, step by step. It saves the loop. It runs it. It keeps running it.
Because the loop is code, it can hold state, interact with your codebase, hit external APIs, post to Slack, and orchestrate multiple subagents in parallel on any combination of models you pick. Cheap open-weight model for the easy work. Frontier model for the hard reasoning. Whatever fits the step.
For a six-agent research swarm, this is exactly the layer that used to be missing.
You can find Slate at [randomlabs.ai](https://randomlabs.ai) ([randomlabs.ai](https://randomlabs.ai/)). It is available today.
Now let me show you the swarm.
Part 3: The Six Agents
Every serious quant fund runs the same six stages of research.
Here is the swarm that replaces them.
> Agent 1: The Idea Generator.
Reads new research papers from arXiv q-fin, SSRN, and financial journals every night.
Studies the mathematical model each paper is proposing. Extracts the exact hypothesis being claimed, the required data, and the direction of the predicted signal.
Writes each hypothesis as a structured research ticket the next agent can pick up.
Runs on a fast cost-efficient model because the task is high-volume structured extraction.
> Agent 2: The Feature Engineer.
Takes a hypothesis ticket. Pulls the required data from the price database or fundamental database.
Constructs the feature vector. Standardizes across the cross-section. Handles missing observations, outliers beyond three standard deviations, and look-ahead bias.
Outputs a clean dataframe ready for backtesting.
> Agent 3: The Backtester.
Takes the feature vector. Builds portfolio construction rules. Runs the historical backtest across 20 years of data with realistic transaction costs, borrowing costs on the short side, and slippage.
Outputs Sharpe ratio, maximum drawdown, turnover, and capacity estimates.
> Agent 4: The Validator.
This is where the rigor lives.
Takes the backtest result. Runs Newey-West adjusted t-statistics to correct for autocorrelation in the return series. Runs bootstrap resampling with 10,000 iterations to check whether the Sharpe is real or a sample artifact.
Flags any signal that fails significance thresholds. Kills anything with an in-sample vs out-of-sample degradation greater than 30 percent, because that is overfitting.
Runs on a stronger reasoning model. The maker never validates the maker's own work. Ever.
> Agent 5: The Regime Auditor.
Takes signals that passed validation. Segments the 20-year history by regime (identified via a Hidden Markov Model on volatility and returns).
Recomputes Sharpe, drawdown, and hit rate inside each regime. Kills anything that only works in one regime, because that is regime timing dressed up as alpha.
> Agent 6: The Factor Decomposer.
Takes regime-robust signals. Regresses them against the Fama-French five factor model plus Carhart momentum plus a low-vol factor.
Reports the residual alpha (the intercept of the regression) and its t-statistic.
Only signals where the residual alpha survives factor decomposition are genuine new alpha. Everything else is repackaged momentum or repackaged value with extra steps.
Six agents. Each one owns one stage. They pass their outputs down the chain.

The whole swarm runs on a Slate Program that fires every 24 hours.
Part 4: How To Build It Step By Step
Here is the exact build. Follow along and you will have the swarm running by end of day.
> Step 1: Install Slate
Open your terminal and run:
Slate installs as a global CLI in under 30 seconds.
Then create the project directory:
slate init scaffolds the project with the folders you need for state, Programs, and providers.
> Step 2: Connect Your Models
Run:
This opens the provider configuration screen inside the Slate CLI. Connect the models you want to use.
For this swarm I use Sonnet on the fast agents (idea generation, feature engineering, backtesting, regime audit) and Opus on the reasoning-heavy agents (validation and factor decomposition).

Step 3: Draft The Program
Start Slate:
> Then in the Slate CLI type:

draft me a program that runs six research agents in sequence: idea generator, feature engineer, backtester, validator, regime auditor, factor decomposer. run it every 24 hours. use sonnet for the fast agents and opus for validation and factor decomposition.
Slate drafts the Program with you. It asks clarifying questions. Which data source. What backtest window. What Sharpe threshold. What regime classifier. You answer in natural language. Slate writes the JavaScript.

Here is what the loop looks like once written:
That is the whole swarm. One file. Six agents. Runs forever.

> Step 4: Run The Swarm
Save the file and run:
The moment you hit enter, Slate spins up the loop. The six agents fire in sequence.
Feature engineering runs in parallel across every hypothesis. Backtests run in parallel. Validation runs on the stronger model.
You can watch every agent working from the Slate CLI in real time. Each agent shows its state, its current task, and its progress.
[Screenshot 4: Terminal showing the swarm running with multiple agents active in parallel, progress indicators visible for each stage.]
The first cycle takes 20 to 40 minutes depending on how many hypotheses stage one produces.
At the end, Slate posts the survivors to your Slack channel with their Sharpe ratios, drawdowns, and residual alpha. Then sleeps until tomorrow.
> Step 5: Iterate
The first version of the loop is never the final one.
> The idea generator will produce duplicates. Type into Slate:

add a check against the state history so it only proposes hypotheses we haven't tested in the last 30 days.
> The validator will reject signals you think should have passed. Type:

loosen the Sharpe threshold to 1.2 but tighten the max drawdown threshold to 8 percent.
Slate updates the Program for you. The next cycle uses the new logic. Every improvement compounds into the state file, and over time the swarm gets sharper because it remembers everything it has already tested and everything it has already rejected.
Part 5: How This Actually Replaces A Research Team
Three patterns cover every real deployment.
Pattern 1: Overnight discovery.
The swarm runs from 8 PM to 8 AM. Every morning you wake up to two or three signals that survived all six stages.
Your job becomes reviewing survivors instead of running the pipeline yourself.
Pattern 2: Hypothesis burst mode.
New paper drops. New data source becomes available. You fire the swarm on demand and get 100 hypotheses tested that afternoon.
A human researcher tests two in the same time.
Pattern 3: Alpha decay monitoring.
The swarm reruns validated signals every week against fresh data. The moment a signal's Sharpe drops below threshold, it flags the decay.
You cut exposure before the drawdown accumulates.
Each pattern replaces a specific function that used to require a PhD. Together they replace most of what a research team actually does day to day.
Part 6: Five Failure Modes That Kill 90 Percent Of Retail Attempts
Failure 1: Skipping the validator.
You will get 100 signals with beautiful Sharpe ratios and no rigor. Every one is data snooping in disguise.
The validator is non-negotiable. Use your strongest model. Set hard rejection thresholds. Never let the maker validate its own work.
Failure 2: No state persistence.
A swarm without memory tests the same failed hypothesis every day.
Every rejected signal must be logged with the exact rejection reason so no agent ever wastes tokens on the same failure twice.
Failure 3: No maker-checker split.
The agent that generated the hypothesis is the worst possible judge of whether it is real alpha.
Split maker and checker across different agents on different models. Renaissance does this. Two Sigma does this. Citadel does this. Your swarm should too.
Failure 4: One agent doing everything.
The moment you try to make one agent generate, engineer, backtest, and validate, quality collapses.
Specialization is what makes the swarm work. Each agent does one thing perfectly.
Failure 5: No stopping condition on the loop.
A loop without a real stop fails silently. The agent emits a completion signal believing the job is done. Bad results sit uncorrected.
Every stopping condition must be checkable by something other than the agent's own claim. "Sharpe above 1.5 over the last 30 out-of-sample trades." "Drawdown below 5 percent." Never "the agent says it is done."
Respect these five and the swarm produces institutional-grade research output.
Summary
Alpha research is already a pipeline. Six stages. Read papers. Engineer features. Backtest. Validate. Check regimes. Decompose against factors.
Every serious fund runs it with 100 PhDs.
A swarm of six specialized AI agents runs every stage for you. Each agent picks the model that fits its complexity. The whole swarm runs on a Slate Program that fires every 24 hours.
Programs by Slate is the layer that makes this actually shippable in a weekend instead of six months.
It drafts the loop with you. It saves the loop. It runs the loop. It runs it forever.
You stop being the pipeline. You become the architect.
The infrastructure moat is real. The research moat is dead.
That is the point.
> If you want to try it, sign up at [randomlabs.ai](https://randomlabs.ai) ([randomlabs.ai](https://randomlabs.ai/)) and follow @wearerandomlabs ([x.com/wearerandomlabs](https://x.com/wearerandomlabs)) for the launch.
In my previous article on loop engineering I broke down how the same architecture wires into a full self-improving trading system that executes trades on its own. If you have not read it yet, read it right after this.

 This swarm is the research half of that system.

[x.com/i/web/status/2069056530960490835](https://x.com/i/web/status/2069056530960490835)
The funds that build this first will compound for the next decade.
The ones still running one hypothesis at a time will be left behind.
So here is the question to sit with.
Are you the researcher still testing one hypothesis a week, or are you the architect who built the swarm that tests a hundred every night while you sleep?
There is no wrong answer. But there are very revealing ones.

![](https://pbs.twimg.com/media/HMYFvP3aEAAgG9R.jpg)

![](https://pbs.twimg.com/media/HMYN0VzaMAAGykX.jpg)

![](https://pbs.twimg.com/media/HMYVJtwaQAA2oxZ.jpg)

![](https://pbs.twimg.com/media/HMYX1B_a4AANhHf.jpg)

![](https://pbs.twimg.com/media/HMYXs0UbkAAQti4.jpg)

![](https://pbs.twimg.com/media/HMYYtw2bIAAK9nu.jpg)
