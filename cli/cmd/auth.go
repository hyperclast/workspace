package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"syscall"

	"github.com/hyperclast/workspace/cli/internal/api"
	"github.com/spf13/cobra"
	"golang.org/x/term"
)

var authCmd = &cobra.Command{
	Use:   "auth",
	Short: "Manage authentication",
	Long:  `Commands for authenticating with Hyperclast.`,
}

var authLoginCmd = &cobra.Command{
	Use:   "login",
	Short: "Authenticate with your API token",
	Long:  `Authenticate with Hyperclast using your API token.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		settingsURL := strings.TrimSuffix(cfg.APIURL, "/api") + "/settings/#developer"

		fmt.Println()
		fmt.Println("To authenticate, you need an API token from Hyperclast.")
		fmt.Println()
		fmt.Printf("  1. Open %s\n", settingsURL)
		fmt.Println("  2. Copy your API token")
		fmt.Println()
		fmt.Print("Enter your API token: ")

		tokenBytes, err := term.ReadPassword(int(syscall.Stdin))
		fmt.Println()
		if err != nil {
			return fmt.Errorf("failed to read token: %w", err)
		}

		token := strings.TrimSpace(string(tokenBytes))

		if token == "" {
			return fmt.Errorf("token cannot be empty")
		}

		printDebug("API URL: %s", cfg.APIURL)
		printDebug("Token length: %d", len(token))

		client := api.NewClient(cfg.APIURL, token)
		user, err := client.GetCurrentUser()
		if err != nil {
			return fmt.Errorf("authentication failed: %w", err)
		}

		cfg.SetToken(token)
		if err := cfg.Save(); err != nil {
			return fmt.Errorf("failed to save config: %w", err)
		}

		printSuccess("Authenticated as %s", user.Email)
		printInfo("Config saved to %s", cfg.Path())

		return nil
	},
}

var authLogoutCmd = &cobra.Command{
	Use:   "logout",
	Short: "Remove stored credentials",
	Long:  `Remove the stored API token from your config file.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		if !cfg.IsAuthenticated() {
			printInfo("Not currently authenticated")
			return nil
		}

		cfg.ClearToken()
		if err := cfg.Save(); err != nil {
			return fmt.Errorf("failed to save config: %w", err)
		}

		printSuccess("Logged out successfully")
		return nil
	},
}

var authStatusCmd = &cobra.Command{
	Use:   "status",
	Short: "Check authentication status",
	Long:  `Show the current authentication status.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		if !cfg.IsAuthenticated() {
			if outputFmt == "json" {
				json.NewEncoder(os.Stdout).Encode(map[string]interface{}{
					"authenticated": false,
				})
				return nil
			}
			printInfo("Not authenticated. Run 'hyperclast auth login' to authenticate.")
			return nil
		}

		client := api.NewClient(cfg.APIURL, cfg.Token)
		user, err := client.GetCurrentUser()
		if err != nil {
			if outputFmt == "json" {
				json.NewEncoder(os.Stdout).Encode(map[string]interface{}{
					"authenticated": false,
					"error":         err.Error(),
				})
				return nil
			}
			return fmt.Errorf("failed to verify token: %w", err)
		}

		if outputFmt == "json" {
			json.NewEncoder(os.Stdout).Encode(map[string]interface{}{
				"authenticated": true,
				"email":         user.Email,
				"external_id":   user.ExternalID,
			})
			return nil
		}

		printSuccess("Authenticated as %s", user.Email)
		return nil
	},
}

func init() {
	rootCmd.AddCommand(authCmd)
	authCmd.AddCommand(authLoginCmd)
	authCmd.AddCommand(authLogoutCmd)
	authCmd.AddCommand(authStatusCmd)
}
