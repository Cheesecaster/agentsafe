// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title AgentRegistry
 * @notice DID-style identity registry for verified autonomous agents on Base.
 * @dev Allows agents to register a name, metadata, and verification badge.
 *      Used by SessionGuard/Escrow to trust or deny unknown agents.
 *      Optimized: 1 slot per agent (address key -> packed struct).
 */
contract AgentRegistry is Ownable {

    struct Agent {
        address wallet;
        bytes32 nameHash;      // keccak256 of agent name
        uint8 trustScore;      // 0-100 (100 = fully verified)
        uint40 registeredAt;   // Timestamp of registration
        uint40 lastUpdate;     // Last profile update
        uint16 metadataLen;    // Length of metadata
    }

    mapping(address => Agent) public agents;
    mapping(bytes32 => address) public nameRegistry; // nameHash -> address

    string[] public metadataStore; // IPFS/Arweave refs for extended agent data
    mapping(address => uint16) public agentMetadataIndex;

    event AgentRegistered(address agent, bytes32 nameHash, string metadataUri);
    event TrustUpdated(address agent, uint8 newScore);
    event AgentVerified(address agent, address verifier);

    event MetadataUpdated(address agent, uint16 index);

    constructor() Ownable(msg.sender) {}

    /**
     * @notice Register an agent identity.
     * @param agent The agent's wallet address.
     * @param name Human-readable name (stored as hash).
     * @param metadataUri IPFS/Arweave URI for extended profile.
     */
    function registerAgent(address agent, string calldata name, string calldata metadataUri) external onlyOwner {
        require(agent != address(0), "Invalid address");
        require(agents[agent].wallet == address(0), "Already registered");

        bytes32 nameHash = keccak256(bytes(name));
        require(nameRegistry[nameHash] == address(0), "Name taken");

        nameRegistry[nameHash] = agent;
        metadataStore.push(metadataUri);
        uint16 idx = uint16(metadataStore.length - 1);

        agents[agent] = Agent({
            wallet: agent,
            nameHash: nameHash,
            trustScore: 10,
            registeredAt: uint40(block.timestamp),
            lastUpdate: uint40(block.timestamp),
            metadataLen: idx
        });

        emit AgentRegistered(agent, nameHash, metadataUri);
    }

    function updateTrust(address agent, uint8 newScore) external onlyOwner {
        require(newScore <= 100, "Score out of range");
        require(agents[agent].wallet != address(0), "Not registered");

        agents[agent].trustScore = newScore;
        agents[agent].lastUpdate = uint40(block.timestamp);
        emit TrustUpdated(agent, newScore);
    }

    function verifyAgent(address agent) external onlyOwner {
        require(agents[agent].wallet != address(0), "Not registered");
        require(agents[agent].trustScore < 100, "Already verified");

        agents[agent].trustScore = 100;
        agents[agent].lastUpdate = uint40(block.timestamp);
        emit AgentVerified(agent, msg.sender);
    }

    function getAgent(address agent) external view returns (
        bytes32 nameHash,
        uint8 trustScore,
        uint40 registeredAt,
        uint40 lastUpdate
    ) {
        Agent storage a = agents[agent];
        return (a.nameHash, a.trustScore, a.registeredAt, a.lastUpdate);
    }

    function isTrusted(address agent, uint8 minScore) external view returns (bool) {
        Agent storage a = agents[agent];
        return a.wallet != address(0) && a.trustScore >= minScore;
    }

    function resolveName(bytes32 nameHash) external view returns (address) {
        return nameRegistry[nameHash];
    }

    function getMetadata(uint16 index) external view returns (string memory) {
        require(index < metadataStore.length, "Index out of bounds");
        return metadataStore[index];
    }
}
