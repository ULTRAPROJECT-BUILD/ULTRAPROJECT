#!/bin/bash
# Injected into context on every user prompt.
# Reminds agents to verify before asserting.
echo "VERIFY BEFORE ASSERTING. Do not state causes, explanations, or system state without evidence from a tool call. If you don't know, say so and investigate."
