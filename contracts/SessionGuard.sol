// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/**
 * @title SessionGuard
 * @notice Manages session keys for autonomous agents with strict DAILY spending caps on Base.
 * @dev Each agent gets a session key. Spend caps reset at midnight UTC.
 */
contract SessionGuard is Ownable {
    
    struct Session {
        address key;
        uint256 dailyLimit;     // Max spend per day (e.g. $20 USDC = 20 * 1e6)
        uint256 spentToday;     // Amount spent in current 24h window
        uint256 lastResetTs;    // Timestamp of start of current day
        bool active;
        uint256 expiresAt;      // Overall session expiration
    }

    IERC20 public immutable USDC;
    mapping(address => Session) public sessions;

    event SessionCreated(address key, uint256 dailyLimit, uint256 expiresAt);
    event LimitUpdated(address key, uint256 newLimit);
    event AgentSpent(address key, uint256 amount, uint256 remainingDaily);
    event SessionRevoked(address key);

    constructor(address _usdcAddress) {
        USDC = IERC20(_usdcAddress);
    }

    /**
     * @notice Create a session for an agent with a specific daily limit.
     * @param agentKey The wallet address of the agent.
     * @param limitWei The daily limit (remember USDC has 6 decimals: $20 = 20_000_000).
     * @param durationDays How many days this session key remains active total.
     */
    function createSession(
        address agentKey, 
        uint256 limitWei, 
        uint256 durationDays
    ) external onlyOwner {
        require(agentKey != address(0), "Invalid address");
        require(!sessions[agentKey].active, "Session exists");
        
        uint256 todayMidnight = (block.timestamp / 1 days) * 1 days;

        sessions[agentKey] = Session({
            key: agentKey,
            dailyLimit: limitWei,
            spentToday: 0,
            lastResetTs: todayMidnight,
            active: true,
            expiresAt: block.timestamp + (durationDays * 1 days)
        });

        emit SessionCreated(agentKey, limitWei, block.timestamp + (durationDays * 1 days));
    }

    /**
     * @notice Update the daily limit of an active session.
     * Can be used to increase or decrease spending power on the fly.
     */
    function updateDailyLimit(address agentKey, uint256 newLimitWei) external onlyOwner {
        require(sessions[agentKey].active, "Session inactive");
        sessions[agentKey].dailyLimit = newLimitWei;
        emit LimitUpdated(agentKey, newLimitWei);
    }

    /**
     * @notice Called by the agent to spend USDC (e.g. pay an API via x402).
     * Logic: 
     * 1. Check session validity.
     * 2. Auto-reset 'spentToday' if 24h window passed.
     * 3. Check against dailyLimit.
     * 4. Transfer USDC from Guard wallet to destination.
     */
    function spend(address destination, uint256 amountWei) external {
        Session storage s = sessions[msg.sender];
        require(s.active, "Session revoked or expired");
        require(block.timestamp < s.expiresAt, "Session expired");

        // 1. Auto-Reset Logic (Midnight UTC)
        uint256 todayMidnight = (block.timestamp / 1 days) * 1 days;
        if (s.lastResetTs < todayMidnight) {
            s.spentToday = 0;
            s.lastResetTs = todayMidnight;
        }

        // 2. Check Daily Cap
        require(s.spentToday + amountWei <= s.dailyLimit, "Daily limit exceeded");

        // 3. Record Spend
        s.spentToday += amountWei;

        // 4. Execute Transfer (Guard holds the funds)
        require(USDC.transfer(destination, amountWei), "Transfer failed");

        emit AgentSpent(msg.sender, amountWei, s.dailyLimit - s.spentToday);
    }

    /**
     * @notice Revoke an agent's spending access instantly.
     */
    function revoke(address agentKey) external onlyOwner {
        require(sessions[agentKey].active, "Session inactive");
        sessions[agentKey].active = false;
        emit SessionRevoked(agentKey);
    }

    /**
     * @notice Helper to check agent status.
     */
    function getSession(address agentKey) external view returns (
        uint256 dailyLimit,
        uint256 spentToday,
        uint256 remaining,
        uint256 expiresAt
    ) {
        Session storage s = sessions[agentKey];
        dailyLimit = s.dailyLimit;
        spentToday = s.spentToday;
        remaining = s.dailyLimit - s.spentToday;
        expiresAt = s.expiresAt;
    }
}
