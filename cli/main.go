package main

import (
	"github.com/hyperclast/workspace/cli/cmd"
	"github.com/hyperclast/workspace/cli/internal/api"
)

func main() {
	api.SetVersion(cmd.Version)
	cmd.Execute()
}
