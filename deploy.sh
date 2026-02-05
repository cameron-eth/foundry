#!/bin/bash
# =============================================================================
# Tool Foundry - Modal Deployment Script
# =============================================================================
# This script helps you deploy Tool Foundry to your own Modal instance.
#
# Prerequisites:
#   1. Python 3.11+ installed
#   2. Modal account (sign up free at https://modal.com)
#   3. Anthropic API key (for AI-driven tool generation)
#
# Usage:
#   ./deploy.sh setup    # First-time setup (secrets, auth)
#   ./deploy.sh serve    # Local development with hot reload
#   ./deploy.sh deploy   # Deploy to production
#   ./deploy.sh status   # Check deployment status
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  Tool Foundry - Modal Deployment${NC}"
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}→ $1${NC}"
}

# Check if Modal is installed
check_modal() {
    if ! command -v modal &> /dev/null; then
        print_error "Modal CLI not found. Installing..."
        pip install modal
    fi
    print_success "Modal CLI is installed"
}

# Check Modal authentication
check_auth() {
    if ! modal token show &> /dev/null; then
        print_warning "Not authenticated with Modal"
        print_info "Running: modal token new"
        modal token new
    fi
    print_success "Authenticated with Modal"
}

# Setup secrets
setup_secrets() {
    echo ""
    print_info "Setting up Modal secrets..."
    echo ""
    
    echo "Tool Foundry supports multiple LLM providers:"
    echo "  1. Anthropic Claude (recommended)"
    echo "  2. OpenAI GPT / Codex 5.2"
    echo ""
    echo "You need at least ONE provider configured."
    echo ""
    
    # Check if anthropic-credentials exists
    if modal secret list 2>/dev/null | grep -q "anthropic-credentials"; then
        print_success "anthropic-credentials secret exists"
    else
        print_warning "anthropic-credentials secret not found"
        echo ""
        read -p "Enter your Anthropic API key (or press Enter to skip): " ANTHROPIC_KEY
        if [ -n "$ANTHROPIC_KEY" ]; then
            modal secret create anthropic-credentials ANTHROPIC_API_KEY="$ANTHROPIC_KEY"
            print_success "Created anthropic-credentials secret"
        else
            print_info "Skipped Anthropic"
        fi
    fi

    # Check if openai-credentials exists
    if modal secret list 2>/dev/null | grep -q "openai-credentials"; then
        print_success "openai-credentials secret exists"
    else
        print_warning "openai-credentials secret not found"
        echo ""
        read -p "Enter your OpenAI API key (or press Enter to skip): " OPENAI_KEY
        if [ -n "$OPENAI_KEY" ]; then
            modal secret create openai-credentials OPENAI_API_KEY="$OPENAI_KEY"
            print_success "Created openai-credentials secret"
            echo ""
            print_info "To use GPT Codex 5.2, set these in foundry-branding secret:"
            echo "  FOUNDRY_LLM_PROVIDER=openai"
            echo "  FOUNDRY_AGENT_MODEL=codex-5.2"
        else
            print_info "Skipped OpenAI"
        fi
    fi

    # Check if exa-credentials exists (optional)
    if modal secret list 2>/dev/null | grep -q "exa-credentials"; then
        print_success "exa-credentials secret exists"
    else
        print_warning "exa-credentials secret not found (optional - for web search)"
        echo ""
        read -p "Enter your Exa API key (or press Enter to skip): " EXA_KEY
        if [ -n "$EXA_KEY" ]; then
            modal secret create exa-credentials EXA_API_KEY="$EXA_KEY"
            print_success "Created exa-credentials secret"
        else
            print_info "Skipped - Web search in tools will be disabled"
        fi
    fi

    echo ""
    print_success "Secrets setup complete"
}

# Setup Swagger/API branding and LLM config
setup_branding() {
    echo ""
    print_info "Setting up API branding & LLM configuration..."
    echo ""
    
    if modal secret list 2>/dev/null | grep -q "foundry-branding"; then
        print_success "foundry-branding secret exists"
        read -p "Do you want to update configuration? (y/N): " UPDATE_BRANDING
        if [ "$UPDATE_BRANDING" != "y" ] && [ "$UPDATE_BRANDING" != "Y" ]; then
            return
        fi
    fi
    
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  LLM Provider Configuration"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "Available providers:"
    echo "  1. anthropic - Claude (default)"
    echo "  2. openai    - GPT / Codex 5.2"
    echo ""
    read -p "LLM Provider [anthropic]: " LLM_PROVIDER
    LLM_PROVIDER="${LLM_PROVIDER:-anthropic}"
    
    if [ "$LLM_PROVIDER" = "openai" ]; then
        echo ""
        echo "Available OpenAI models:"
        echo "  - codex-5.2 (recommended for code generation)"
        echo "  - gpt-4o"
        echo "  - gpt-4o-mini (faster, cheaper)"
        echo ""
        read -p "Model [codex-5.2]: " AGENT_MODEL
        AGENT_MODEL="${AGENT_MODEL:-codex-5.2}"
    else
        echo ""
        echo "Available Anthropic models:"
        echo "  - claude-sonnet-4-20250514 (recommended)"
        echo "  - claude-3-5-sonnet-20241022"
        echo ""
        read -p "Model [claude-sonnet-4-20250514]: " AGENT_MODEL
        AGENT_MODEL="${AGENT_MODEL:-claude-sonnet-4-20250514}"
    fi
    
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  API Branding (Swagger Docs)"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    
    read -p "API Title [Tool Foundry API]: " API_TITLE
    API_TITLE="${API_TITLE:-Tool Foundry API}"
    
    read -p "API Description (custom tagline): " API_DESC
    
    read -p "Logo URL (for Swagger header): " LOGO_URL
    
    read -p "Contact Name: " CONTACT_NAME
    
    read -p "Contact Email: " CONTACT_EMAIL
    
    read -p "Contact URL: " CONTACT_URL
    
    # Create or update the secret
    modal secret create foundry-branding \
        FOUNDRY_LLM_PROVIDER="$LLM_PROVIDER" \
        FOUNDRY_AGENT_MODEL="$AGENT_MODEL" \
        FOUNDRY_API_TITLE="$API_TITLE" \
        FOUNDRY_API_DESCRIPTION="$API_DESC" \
        FOUNDRY_LOGO_URL="$LOGO_URL" \
        FOUNDRY_CONTACT_NAME="$CONTACT_NAME" \
        FOUNDRY_CONTACT_EMAIL="$CONTACT_EMAIL" \
        FOUNDRY_CONTACT_URL="$CONTACT_URL" \
        --force 2>/dev/null || \
    modal secret create foundry-branding \
        FOUNDRY_LLM_PROVIDER="$LLM_PROVIDER" \
        FOUNDRY_AGENT_MODEL="$AGENT_MODEL" \
        FOUNDRY_API_TITLE="$API_TITLE" \
        FOUNDRY_API_DESCRIPTION="$API_DESC" \
        FOUNDRY_LOGO_URL="$LOGO_URL" \
        FOUNDRY_CONTACT_NAME="$CONTACT_NAME" \
        FOUNDRY_CONTACT_EMAIL="$CONTACT_EMAIL" \
        FOUNDRY_CONTACT_URL="$CONTACT_URL"
    
    echo ""
    print_success "Configuration saved!"
    echo ""
    echo "  LLM Provider: $LLM_PROVIDER"
    echo "  Model: $AGENT_MODEL"
    echo "  API Title: $API_TITLE"
    echo ""
}

# Local development server
serve() {
    print_info "Starting local development server..."
    print_info "API will be available at the URL shown below"
    print_info "Press Ctrl+C to stop"
    echo ""
    modal serve foundry.py
}

# Deploy to production
deploy() {
    print_info "Deploying to Modal..."
    echo ""
    modal deploy foundry.py
    echo ""
    print_success "Deployment complete!"
    echo ""
    print_info "Your API is now live at:"
    echo ""
    # Get workspace from modal config
    WORKSPACE=$(modal config show 2>/dev/null | grep workspace | awk '{print $2}' || echo "{your-workspace}")
    echo "  https://${WORKSPACE}--toolfoundry-serve.modal.run"
    echo ""
    print_info "Swagger docs:"
    echo "  https://${WORKSPACE}--toolfoundry-serve.modal.run/docs"
    echo ""
}

# Check status
status() {
    print_info "Checking deployment status..."
    echo ""
    modal app list | grep -E "(toolfoundry|Name)" || print_warning "No toolfoundry app found"
    echo ""
    print_info "Running functions:"
    modal function list 2>/dev/null | grep -E "(toolfoundry|Function)" || print_info "No functions running"
}

# Main command handler
main() {
    print_header
    
    case "${1:-help}" in
        setup)
            check_modal
            check_auth
            setup_secrets
            echo ""
            read -p "Would you like to customize API branding (Swagger docs)? (y/N): " SETUP_BRAND
            if [ "$SETUP_BRAND" = "y" ] || [ "$SETUP_BRAND" = "Y" ]; then
                setup_branding
            fi
            echo ""
            print_success "Setup complete! Run './deploy.sh deploy' to deploy."
            ;;
        branding)
            check_modal
            check_auth
            setup_branding
            print_info "Run './deploy.sh deploy' to apply branding changes."
            ;;
        serve)
            check_modal
            check_auth
            serve
            ;;
        deploy)
            check_modal
            check_auth
            deploy
            ;;
        status)
            check_modal
            status
            ;;
        help|*)
            echo ""
            echo "Usage: $0 <command>"
            echo ""
            echo "Commands:"
            echo "  setup    - First-time setup (install, auth, secrets)"
            echo "  branding - Configure API branding (title, logo, contact)"
            echo "  serve    - Start local development server"
            echo "  deploy   - Deploy to Modal production"
            echo "  status   - Check deployment status"
            echo ""
            echo "Quick Start:"
            echo "  1. ./deploy.sh setup"
            echo "  2. ./deploy.sh deploy"
            echo ""
            echo "Customize Swagger docs:"
            echo "  ./deploy.sh branding"
            echo ""
            ;;
    esac
}

main "$@"
