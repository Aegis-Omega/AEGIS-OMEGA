// AEGIS-Ω Go Client
// Connects any Go service to the AEGIS constitutional swarm.
// The shared language: PlatformEnvelope[T] — same JSON schema regardless of caller.
//
// Usage:
//   go run client.go "Enter EU fintech market Q4 2026" gtm
//
// No dependencies beyond stdlib.

package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

const baseURL = "https://aegis-vertex.aegisomega.com"

type collaborateRequest struct {
	Objective string `json:"objective"`
	Mode      string `json:"mode"`
	Live      bool   `json:"live"`
}

type platformEnvelope struct {
	ContractVersion        string          `json:"contract_version"`
	ExecutionID            string          `json:"execution_id"`
	Timestamp              string          `json:"timestamp"`
	IsReplayReconstructable bool           `json:"is_replay_reconstructable"`
	Data                   json.RawMessage `json:"data"`
}

type collaborateData struct {
	CycleID               string          `json:"cycle_id"`
	Objective             string          `json:"objective"`
	Mode                  string          `json:"mode"`
	DepartmentsCollaborated int           `json:"departments_collaborated"`
	ConstitutionalAudit   json.RawMessage `json:"constitutional_audit"`
	AuditChainHash        string          `json:"audit_chain_hash"`
	ChainValid            bool            `json:"chain_valid"`
}

func collaborate(objective, mode string) (*collaborateData, error) {
	body, _ := json.Marshal(collaborateRequest{Objective: objective, Mode: mode, Live: false})

	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Post(baseURL+"/platform/collaborate", "application/json", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, raw)
	}

	var envelope platformEnvelope
	if err := json.Unmarshal(raw, &envelope); err != nil {
		return nil, fmt.Errorf("parse envelope: %w", err)
	}
	if envelope.ContractVersion != "1.0.0" {
		return nil, fmt.Errorf("unsupported contract_version: %s", envelope.ContractVersion)
	}
	if !envelope.IsReplayReconstructable {
		return nil, fmt.Errorf("is_replay_reconstructable must be true")
	}

	var data collaborateData
	if err := json.Unmarshal(envelope.Data, &data); err != nil {
		return nil, fmt.Errorf("parse data: %w", err)
	}
	return &data, nil
}

func main() {
	objective := "Identify best revenue opportunity"
	mode := "revenue"
	if len(os.Args) > 1 {
		objective = os.Args[1]
	}
	if len(os.Args) > 2 {
		mode = os.Args[2]
	}

	fmt.Printf("AEGIS-Ω  objective=%q  mode=%s\n", objective, mode)

	result, err := collaborate(objective, mode)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("cycle_id:    %s\n", result.CycleID)
	fmt.Printf("departments: %d\n", result.DepartmentsCollaborated)
	fmt.Printf("chain_valid: %v\n", result.ChainValid)
	fmt.Printf("audit:       %s\n", result.ConstitutionalAudit)
}
