// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title AgentRegistry
 * @notice Registry for AI agents with trust scoring and verification.
 *         Agents register with a name and metadata URI, receive trust scores (0-100),
 *         and verified agents are auto-assigned the maximum score.
 */
contract AgentRegistry {
    /// @notice Agent record
    struct Agent {
        string name;           // Human-readable agent name
        string metadataURI;    // IPFS or HTTP link to agent metadata
        uint8  trustScore;     // Trust score 0-100
        bool   verified;       // Whether the agent is verified (auto-score=100)
        uint48 registeredAt;   // Registration timestamp
        address registeredBy;  // Address that registered the agent
    }

    /// @notice Agent address -> Agent record
    mapping(address => Agent) public agents;

    /// @notice All registered agent addresses (for enumeration)
    address[] public agentList;

    /// @notice Governance/admin address
    address public owner;

    event AgentRegistered(address agentAddr, string name, string metadataURI);
    event TrustUpdated(address agentAddr, uint8 newScore, address updatedBy);
    event AgentVerified(address agentAddr);
    event OwnershipTransferred(address oldOwner, address newOwner);

    modifier onlyOwner() {
        require(msg.sender == owner, "AgentRegistry: caller is not owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /**
     * @notice Register a new agent. Anyone can register their own agent address.
     * @param name Human-readable name for the agent
     * @param metadataURI URI to agent metadata
     */
    function registerAgent(string calldata name, string calldata metadataURI) external {
        require(bytes(name).length > 0, "AgentRegistry: name is empty");
        require(agents[msg.sender].registeredAt == 0, "AgentRegistry: already registered");

        agents[msg.sender] = Agent({
            name: name,
            metadataURI: metadataURI,
            trustScore: 0,
            verified: false,
            registeredAt: uint48(block.timestamp),
            registeredBy: msg.sender
        });

        agentList.push(msg.sender);

        emit AgentRegistered(msg.sender, name, metadataURI);
    }

    /**
     * @notice Update the trust score for an agent. Caller must be owner or the agent itself.
     * @param agentAddr Address of the agent
     * @param score New trust score (0-100)
     */
    function updateTrust(address agentAddr, uint8 score) external {
        require(agents[agentAddr].registeredAt > 0, "AgentRegistry: agent not registered");
        require(msg.sender == owner || msg.sender == agentAddr,
                "AgentRegistry: unauthorized trust update");
        require(!agents[agentAddr].verified || msg.sender == owner,
                "AgentRegistry: cannot lower verified agent trust");

        agents[agentAddr].trustScore = score;

        emit TrustUpdated(agentAddr, score, msg.sender);
    }

    /**
     * @notice Verify an agent — auto-assigns maximum trust score (100). Owner only.
     * @param agentAddr Address of the agent to verify
     */
    function verifyAgent(address agentAddr) external onlyOwner {
        require(agents[agentAddr].registeredAt > 0, "AgentRegistry: agent not registered");

        Agent storage agent = agents[agentAddr];
        agent.verified = true;
        agent.trustScore = 100;

        emit AgentVerified(agentAddr);
    }

    /**
     * @notice Check if an agent meets the minimum trust threshold.
     * @param addr Agent address to check
     * @param minScore Minimum trust score required
     * @return True if the agent is registered and meets or exceeds the minimum score
     */
    function isTrusted(address addr, uint8 minScore) external view returns (bool) {
        Agent storage agent = agents[addr];
        if (agent.registeredAt == 0) return false;
        return agent.trustScore >= minScore;
    }

    /**
     * @notice Get full agent details.
     * @param addr Agent address
     */
    function getAgent(address addr)
        external
        view
        returns (
            string memory name,
            string memory metadataURI,
            uint8 trustScore,
            bool verified,
            uint48 registeredAt,
            address registeredBy
        )
    {
        Agent storage agent = agents[addr];
        require(agent.registeredAt > 0, "AgentRegistry: agent not registered");

        return (
            agent.name,
            agent.metadataURI,
            agent.trustScore,
            agent.verified,
            agent.registeredAt,
            agent.registeredBy
        );
    }

    /**
     * @notice Return total number of registered agents.
     */
    function getAgentCount() external view returns (uint256) {
        return agentList.length;
    }

    /**
     * @notice Transfer ownership to a new address.
     */
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "AgentRegistry: new owner is zero address");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }
}
