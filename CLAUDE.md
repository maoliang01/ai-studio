# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 基本规则

- **永远使用中文与用户对话**，包括代码注释、输出信息、error 消息解释等全部使用中文
- 仅在代码本身（如变量名、函数名、配置文件）或用户明确要求时使用英文

## 项目状态

此目录目前为空，是新项目的起点。

## 初始化新项目

当用户需要开始一个新项目时：

1. **先询问需求**：项目类型、使用的技术栈、是否需要现有项目作为参考
2. **遵循简洁优先原则**：不添加用户未请求的功能
3. **主动澄清**：遇到歧义时列出选项供用户选择

### 常见项目初始化

**Node.js/TypeScript 项目：**
```bash
npm init -y
npm install -D typescript @types/node
npx tsc --init
```

**Python 项目：**
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

**Rust 项目：**
```bash
cargo init
```

## 后续步骤

项目启动后，更新本文件添加：
- 项目的特定命令（构建、测试、lint 等）
- 项目的架构说明
- 依赖和工具链信息