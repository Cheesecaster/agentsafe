// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/**
 * @title SessionGuard
 * @notice Manages spending sessions with configurable daily limits for AI agents.
 *         Uses storage packing: uint128 for amounts, uint48 for timestamps.
 */
contract SessionGuard is ReentrancyGuard {
    using SafeERC20 for IERC20;

    /// @notice USDC on Base (6 decimals)
    IERC20 public constant USDC = IERC20(0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913);
    /// @notice 86400 seconds in a day
    uint48 public constant DAY_SECONDS = 86400;

    /// @notice Storage-packed session struct (fits in 3 slots max)
    struct Session {
        uint128 dailyLimit;       // Daily spending limit in USDC (6 decimals)
        uint128 spentToday;       // Amount spent this period in USDC (6 decimals)
        uint48 lastReset;         // Timestamp when the spending counter was reset
        uint48 createdAt;         // Session creation timestamp
        bool active;              // Whether the session is active
        uint8 trustMin;           // Minimum trust score required (0-100)
    }

    /// @notice Session key -> Session data
    mapping(bytes32 => Session) public sessions;

    /// @notice Session ID -> owning key (reverse lookup)
    mapping(bytes32 => bytes32) public sessionIdToKey;

    /// @notice Counter for deterministic yet unique session IDs
    uint256 private _sessionCounter;

    event SessionCreated(bytes32 keyed, bytes32 sessionId, uint128 dailyLimit, uint8 trustMin);
    event SessionKilled(bytes32 keyed, bytes32 sessionId);
    event DailyLimitSet(bytes32 keyed, uint128 newLimit);
    event AgentSpent(bytes32 keyed, bytes32 sessionId, address destination, uint128 amount, uint128 remainingDaily);
    event FundsWithdrawn(address indexed to, uint256 amount);

    /**
     * @notice Create a new spending session.
     * @param keyed Unique identifier for the session owner
     * @param dailyLimitUsd Maximum daily spend in USDC (6 decimals)
     * @param trustMin Minimum trust score required to use the session (0-100)
     * @return sessionId The generated session identifier
     */
    function createSession(
        bytes32 keyed,
        uint128 dailyLimitUsd,
        uint8 trustMin
    ) external returns (bytes32 sessionId) {
        require(dailyLimitUsd > 0, "SessionGuard: daily limit must be > 0");
        require(!sessions[keyed].active, "SessionGuard: session already exists");

        _sessionCounter++;
        sessionId = keccak256(abi.encodePacked(keyed, _sessionCounter, block.timestamp));

        sessions[keyed] = Session({
            dailyLimit: dailyLimitUsd,
            spentToday: 0,
            lastReset: uint48(block.timestamp),
            createdAt: uint48(block.timestamp),
            active: true,
            trustMin: trustMin
        });
        sessionIdToKey[sessionId] = keyed;

        emit SessionCreated(keyed, sessionId, dailyLimitUsd, trustMin);
    }

    /**
     * @notice Spend USDC from a session's daily allowance.
     * @dev Caller must have approved or funded this contract with enough USDC.
     * @param keyed The session owner's key
     * @param sessionId The session identifier
     * @param destination Address to receive USDC
     * @param amountUsd Amount in USDC (6 decimals)
     */
    function spend(
        bytes32 keyed,
        bytes32 sessionId,
        address destination,
        uint128 amountUsd
    ) external nonReentrant {
        Session storage session = sessions[keyed];
        require(session.active, "SessionGuard: session not active");
        require(sessionIdToKey[sessionId] == keyed, "SessionGuard: session key mismatch");
        require(amountUsd > 0, "SessionGuard: amount must be > 0");

        // Auto-reset daily rolling window
        if (uint48(block.timestamp) >= session.lastReset + DAY_SECONDS) {
            session.spentToday = 0;
            session.lastReset = uint48(block.timestamp);
        }

        require(
            session.spentToday + amountUsd <= session.dailyLimit,
            "SessionGuard: daily limit exceeded"
        );

        // Transfer USDC from this contract to destination
        USDC.safeTransfer(destination, amountUsd);
        session.spentToday += amountUsd;

        uint128 remaining = session.dailyLimit - session.spentToday;
        emit AgentSpent(keyed, sessionId, destination, amountUsd, remaining);
    }

    /**
     * @notice View session details.
     */
    function getSession(bytes32 keyed)
        external
        view
        returns (
            uint128 dailyLimit,
            uint128 spentToday,
            uint48 lastReset,
            uint48 createdAt,
            bool active,
            uint8 trustMin
        )
    {
        Session storage s = sessions[keyed];
        return (s.dailyLimit, s.spentToday, s.lastReset, s.createdAt, s.active, s.trustMin);
    }

    /**
     * @notice Update the daily spending limit on an existing session.
     */
    function setDailyLimit(bytes32 keyed, uint128 newLimit) external {
        Session storage session = sessions[keyed];
        require(session.active, "SessionGuard: session not active");
        require(newLimit > 0, "SessionGuard: limit must be > 0");

        session.dailyLimit = newLimit;
        emit DailyLimitSet(keyed, newLimit);
    }

    /**
     * @notice Deactivate a session permanently.
     */
    function killSession(bytes32 keyed) external {
        Session storage session = sessions[keyed];
        require(session.active, "SessionGuard: session not active");
        session.active = false;
        emit SessionKilled(keyed, _sessionIdOf(keyed));
    }

    /**
     * @notice Withdraw any ERC20 tokens held by this contract.
     */
    function withdraw(IERC20 token, address to, uint256 amount) external nonReentrant {
        token.safeTransfer(to, amount);
        emit FundsWithdrawn(to, amount);
    }

    /**
     * @notice Helper to look up the session ID for a keyed operator.
     */
    function _sessionIdOf(bytes32 keyed) internal view returns (bytes32) {
        // Simple forward lookup — in production use a reverse mapping
        return keccak256(abi.encodePacked(keyed));
    }
}
