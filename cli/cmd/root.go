package cmd

import (
	"fmt"
	"os"

	"github.com/hyperclast/workspace/cli/internal/config"
	"github.com/spf13/cobra"
)

var (
	cfgFile   string
	apiURL    string
	outputFmt string
	quiet     bool
	verbose   bool
	cfg       *config.Config
)

var rootCmd = &cobra.Command{
	Use:   "hyperclast",
	Short: "CLI for Hyperclast",
	Long:  `A command-line interface for interacting with Hyperclast. Pipe command output directly to pages, manage projects, and more.`,
	PersistentPreRunE: func(cmd *cobra.Command, args []string) error {
		if cmd.Name() == "help" || cmd.Name() == "version" {
			return nil
		}

		var err error
		cfg, err = config.Load(cfgFile)
		if err != nil {
			return err
		}

		if apiURL != "" {
			cfg.APIURL = apiURL
		}
		return nil
	},
}

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		os.Exit(1)
	}
}

func init() {
	rootCmd.PersistentFlags().StringVar(&cfgFile, "config", "", "config file (default: ~/.config/hyperclast/config.yaml)")
	rootCmd.PersistentFlags().StringVar(&apiURL, "api-url", "", "API URL (default: https://hyperclast.com/api)")
	rootCmd.PersistentFlags().StringVar(&outputFmt, "output", "text", "output format: text, json")
	rootCmd.PersistentFlags().BoolVar(&quiet, "quiet", false, "suppress info messages")
	rootCmd.PersistentFlags().BoolVar(&verbose, "verbose", false, "show debug output")
}

func printSuccess(format string, a ...interface{}) {
	if !quiet {
		fmt.Printf("✓ "+format+"\n", a...)
	}
}

func printInfo(format string, a ...interface{}) {
	if !quiet {
		fmt.Printf(format+"\n", a...)
	}
}

func printError(format string, a ...interface{}) {
	fmt.Fprintf(os.Stderr, "Error: "+format+"\n", a...)
}

func printDebug(format string, a ...interface{}) {
	if verbose {
		fmt.Printf("[DEBUG] "+format+"\n", a...)
	}
}
