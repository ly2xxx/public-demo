# Building production ready AI Agents on Amazon EKS

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US

## Welcome!

This workshop is designed to run at AWS-hosted events using Workshop Studio provisioned accounts. It is not supported in customer-owned AWS accounts.

Here you'll learn how to build, deploy, and operate AI agents on Amazon EKS. We'll do it twice: once with open-source components running entirely on your cluster, and once with AWS managed services plugged in. Same agent, different substrate.

## What you'll learn

- Deploying LLMs on EKS using vLLM on AWS Inferentia chips
- Building AI agents with the Strands Agents SDK
- Observability using Langfuse hosted on EKS
- Memory management using Milvus (vector DB) and Amazon AgentCore Memory
- Agent tool access using MCP and AgentCore managed sandboxes
- Multi-agent interaction using the A2A protocol

## Workshop structure

Two tracks. Both land on the same working agent.

- **Self-managed GenAI Strategy:** everything on EKS: model serving (vLLM on Inferentia), observability (Langfuse), memory (Milvus), tools (MCP)
- **Integrated GenAI Strategy:** EKS plus AWS managed services: Amazon Bedrock, AgentCore Memory, AgentCore Browser + Code Interpreter

## Target audience

A 300+ level workshop for platform, ML, and software engineers building agents on Kubernetes.

## Prerequisites

- Basic Kubernetes concepts (pods, deployments, services)
- Python familiarity
- A general idea of what LLMs and agents are
</content>
