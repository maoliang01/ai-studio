#!/bin/bash
# ===========================================
# AI Studio PostgreSQL 安装脚本（跨平台）
# ===========================================

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  AI Studio PostgreSQL 安装${NC}"
echo -e "${GREEN}========================================${NC}"
echo

# 检测操作系统
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -f /etc/debian_version ]; then
            echo "debian"
        elif [ -f /etc/redhat-release ]; then
            echo "redhat"
        else
            echo "linux"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
        echo "windows"
    else
        echo "unknown"
    fi
}

OS=$(detect_os)
echo -e "检测到操作系统: ${YELLOW}${OS}${NC}"
echo

# 函数：检查 PostgreSQL 是否已安装
check_postgres() {
    if command -v psql &> /dev/null; then
        VERSION=$(psql --version | grep -oE '[0-9]+' | head -1)
        echo -e "${GREEN}✓ PostgreSQL 已安装 (版本 $VERSION)${NC}"
        return 0
    else
        return 1
    fi
}

# 函数：检查数据库是否已创建
check_database() {
    if psql -U postgres -lqt | cut -d \| -f 1 | grep -qw "ai_studio"; then
        echo -e "${GREEN}✓ 数据库 ai_studio 已存在${NC}"
        return 0
    else
        return 1
    fi
}

# 安装 PostgreSQL (debian/ubuntu)
install_debian() {
    echo -e "${YELLOW}[1/3] 更新软件包列表...${NC}"
    sudo apt update

    echo -e "${YELLOW}[2/3] 安装 PostgreSQL...${NC}"
    sudo apt install -y postgresql postgresql-contrib

    echo -e "${YELLOW}[3/3] 配置 PostgreSQL...${NC}"
    sudo -u postgres createuser -s $(whoami) 2>/dev/null || true
    sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';" 2>/dev/null || true

    # 启动服务
    sudo systemctl start postgresql 2>/dev/null || sudo service postgresql start 2>/dev/null || true
    sudo systemctl enable postgresql 2>/dev/null || true
}

# 安装 PostgreSQL (macOS)
install_macos() {
    echo -e "${YELLOW}[1/3] 检查 Homebrew...${NC}"
    if ! command -v brew &> /dev/null; then
        echo -e "${RED}错误: 需要安装 Homebrew${NC}"
        echo "请访问: https://brew.sh"
        exit 1
    fi

    echo -e "${YELLOW}[2/3] 安装 PostgreSQL...${NC}"
    brew install postgresql@15

    echo -e "${YELLOW}[3/3] 配置 PostgreSQL...${NC}"
    export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"

    # 启动服务
    brew services start postgresql@15 2>/dev/null || true
}

# 安装 PostgreSQL (Windows)
install_windows() {
    echo -e "${YELLOW}Windows 系统检测到${NC}"

    # 检查各种可能的包管理器路径
    local WINGET=""
    local CHOCO=""

    # Winget 可能在 WindowsApps 中
    if [ -f "/c/Users/weiji/AppData/Local/Microsoft/WindowsApps/winget.exe" ]; then
        WINGET="/c/Users/weiji/AppData/Local/Microsoft/WindowsApps/winget.exe"
    elif command -v winget &> /dev/null; then
        WINGET="winget"
    fi

    # Chocolatey
    if [ -f "/c/ProgramData/chocolatey/bin/choco.exe" ]; then
        CHOCO="/c/ProgramData/chocolatey/bin/choco.exe"
    elif command -v choco &> /dev/null; then
        CHOCO="choco"
    fi

    if [ -n "$CHOCO" ]; then
        echo -e "${YELLOW}[1/3] 使用 Chocolatey 安装 PostgreSQL...${NC}"
        $CHOCO install postgresql --version=15 -y
    elif [ -n "$WINGET" ]; then
        echo -e "${YELLOW}[1/3] 使用 Winget 安装 PostgreSQL...${NC}"
        cmd.exe /c "$WINGET install PostgreSQL.PostgreSQL --accept-source-agreements --accept-package-agreements"
    else
        echo -e "${RED}错误: 未检测到包管理器${NC}"
        echo ""
        echo "请选择以下方式安装 PostgreSQL:"
        echo ""
        echo "方法 1: 使用 Winget (推荐，Windows 10+ 自带)"
        echo "  按 Win+X 打开 Windows Terminal，输入:"
        echo "  winget install PostgreSQL.PostgreSQL"
        echo ""
        echo "方法 2: 使用 Chocolatey"
        echo "  https://chocolatey.org/install"
        echo "  choco install postgresql"
        echo ""
        echo "方法 3: 手动下载安装程序"
        echo "  https://www.postgresql.org/download/windows/"
        echo ""
        echo "安装完成后请重新运行 ./start.sh"
        exit 1
    fi

    echo -e "${YELLOW}[2/3] 配置 PostgreSQL...${NC}"
    # 设置 postgres 用户密码 - 需要等待安装完成
    sleep 5
    export PGPASSWORD=postgres
    psql -U postgres -h localhost -c "ALTER USER postgres PASSWORD 'postgres';" 2>/dev/null || true
}

# 创建数据库
create_database() {
    echo -e "${YELLOW}创建数据库 ai_studio...${NC}"

    export PGPASSWORD=postgres

    # macOS 使用当前用户
    if [ "$OS" == "macos" ]; then
        createdb ai_studio 2>/dev/null || true
    else
        sudo -u postgres createdb ai_studio 2>/dev/null || \
        psql -U postgres -c "CREATE DATABASE ai_studio;" 2>/dev/null || true
    fi

    echo -e "${GREEN}✓ 数据库创建完成${NC}"
}

# 主流程
main() {
    # 检查 PostgreSQL
    if check_postgres; then
        echo -e "${GREEN}[完成] PostgreSQL 检查通过${NC}"
    else
        echo -e "${YELLOW}[安装] 开始安装 PostgreSQL...${NC}"
        case $OS in
            debian) install_debian ;;
            redhat)
                echo -e "${YELLOW}检测到 RedHat/CentOS 系统${NC}"
                sudo yum install -y postgresql-server postgresql-contrib
                sudo postgresql-setup --initdb || true
                sudo systemctl start postgresql || true
                sudo systemctl enable postgresql || true
                ;;
            macos) install_macos ;;
            windows) install_windows ;;
            *)
                echo -e "${RED}错误: 不支持的操作系统${NC}"
                exit 1
                ;;
        esac
    fi

    # 创建数据库
    echo
    if check_database; then
        echo -e "${GREEN}[完成] 数据库检查通过${NC}"
    else
        create_database
    fi

    echo
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  PostgreSQL 安装完成！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo
    echo "数据库连接信息:"
    echo "  主机: localhost"
    echo "  端口: 5432"
    echo "  数据库: ai_studio"
    echo "  用户名: postgres"
    echo "  密码: postgres"
    echo
    echo "下一步: ./start.sh"
}

main