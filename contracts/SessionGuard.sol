// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppedown/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

/**
 * @title SessionGuard
 * @notice Manages session keys for autonomous agents with strict spending caps on Base.
 * @dev Each session key has a daily or total spending limit.
 */
contract SessionGuard is Ownable, ReentrancyGuard {
    
    struct Session {
        address key;
        uint256 limit;
        uint256 spent;
        bool active;
        uint256 expiresAt;
    }

    address public immutable USDC;
    mapping(address => Session) public sessions;
    mapping(address => bool) public approvedTokens;

    event SessionGranted(address key, uint256 limit, uint256 expiresAt);
    event SessionRevoked(address key);
    event FundsSpent(address key, address token, uint256 amount);

    constructor(address _usdc) Ownable(msg.sender) {
        require(_usdc != address(0), "Invalid USDC address");
        USDC = _usdc;
        approvedTokens[_usdc] = true;
    }

    /**
     * @notice Grant a session key with a spending limit.
     * @param key The address allowed to spend.
     * @param limit The maximum amount of USDC this key can spend.
     * @param duration How long the key is valid (in seconds).
     */
    function grantSession(address key, uint256 limit, uint64 duration) external onlyOwner {
        require(key != address(0), "Invalid key");
        require(!sessions[key].active, "Session already active");

        sessions[key] = Session({
            key: key,
            limit: limit,
            spent: 0,
            active: true,
            expiresAt: block.timestamp + duration
        });

        emit SessionGranted(key, limit, block.timestamp + duration);
    }

    /**
     * @notice Spend USDC using a session key.
     * Must be called by the session key itself.
     * @param amount Amount of USDC to spend.
     */
    function spend(uint256 amount) external nonReentrant {
        Session storage session = sessions[msg.sender];
        require(session.active, "Session inactive");
        require(block.timestamp <= session.expiresAt, "Session expired");
        require(session.spent + amount <= session.limit, "Limit exceeded");

        // Transfer USDC from owner to msg.sender
        // NOTE: This assumes the contract holds the funds or has allowance.
        // In a real agent setup, the agent wallet is separate, but this guard
        // enforces the limit via logic.
        
        session.spent += amount;
        emit FundsSpent(msg.sender, USDC, amount);
    }

    /**
     * @notice Revoke a session key.
     */
    function revokeSession(address key) external onlyOwner {
        require(sessions[key].active, "No active session");
        sessions[key].active = false;
        emit SessionRevoked(key);
    }

    /**
     * @notice Get session details.
     */
    function getSession(address key) external view returns (Session memory) {
        return sessions[key];
    }
}
