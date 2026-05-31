// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title SessionGuard
 * @notice Manages session keys for autonomous agents with strict DAILY spending caps on Base.
 * @dev Optimized for Base (chainId 8453): low gas, high throughput x402 settlements.
 *      Storage packed: Session struct fits in 3 slots (48 bytes).
 *      Uses SafeERC20 for secure USDC transfers (Base USDC: 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913).
 */
contract SessionGuard is Ownable, ReentrancyGuard {

    struct Session {
        uint128 dailyLimit;     // Max spend per day (e.g. $20 USDC = 20_000_000)
        uint128 spentToday;     // Amount spent in current 24h window
        uint40 active;          // 1 = active, 0 = revoked
        uint48 expiresAt;       // Overall session expiration (year ~2^48)
        uint48 lastResetTs;     // Timestamp of start of current day
    }

    IERC20 public immutable USDC;
    mapping(address => Session) private sessions;

    event SessionCreated(address key, uint128 dailyLimit, uint48 expiresAt);
    event LimitUpdated(address key, uint128 newLimit);
    event AgentSpent(
        address key,
        bytes32 sessionId,     // Agent identity hash
        address destination,
        uint128 amount,
        uint128 remainingDaily
    );
    event SessionRevoked(address key);
    event FundsWithdrawn(address owner, uint128 amount);

    constructor(address _usdcAddress) Ownable(msg.sender) {
        require(_usdcAddress != address(0), "Invalid USDC");
        USDC = IERC20(_usdcAddress);
    }

    function deposit(uint128 amount) external nonReentrant {
        require(amount > 0, "Amount must be > 0");
        SafeERC20.safeTransferFrom(USDC, msg.sender, address(this), amount);
    }

    function withdraw(uint128 amount) external onlyOwner nonReentrant {
        require(amount > 0, "Amount must be > 0");
        require(SafeERC20.forceApprove(USDC, msg.sender, 0) || true, "Reset approval");
        uint256 balance = USDC.balanceOf(address(this));
        require(amount <= balance, "Insufficient balance");
        SafeERC20.safeTransfer(USDC, msg.sender, amount);
        emit FundsWithdrawn(msg.sender, amount);
    }

    function createSession(
        address agentKey,
        uint128 limitWei,
        uint48 durationDays
    ) external onlyOwner nonReentrant {
        require(agentKey != address(0), "Invalid address");
        require(sessions[agentKey].active == 0, "Session exists");
        require(limitWei > 0, "Limit must be > 0");

        uint48 todayMidnight = uint48((block.timestamp / 1 days) * 1 days);
        uint48 expiry = uint48(block.timestamp) + uint48(durationDays * 1 days);

        sessions[agentKey] = Session({
            dailyLimit: limitWei,
            spentToday: 0,
            active: 1,
            expiresAt: expiry,
            lastResetTs: todayMidnight
        });

        emit SessionCreated(agentKey, limitWei, expiry);
    }

    function updateDailyLimit(address agentKey, uint128 newLimitWei) external onlyOwner {
        require(sessions[agentKey].active == 1, "Session inactive");
        require(newLimitWei > 0, "Limit must be > 0");

        uint48 todayMidnight = uint48((block.timestamp / 1 days) * 1 days);
        Session storage s = sessions[agentKey];
        if (s.lastResetTs < todayMidnight) {
            s.spentToday = 0;
            s.lastResetTs = todayMidnight;
        }

        s.dailyLimit = newLimitWei;
        emit LimitUpdated(agentKey, newLimitWei);
    }

    /**
     * @notice Called by the agent to spend USDC for x402 payments.
     * @param sessionId bytes32 identity hash from X-Agent-Session header.
     * @param destination Recipient (API provider, service, etc.)
     * @param amountWei Amount in USDC base units (6 decimals).
     */
    function spend(
        bytes32 sessionId,
        address destination,
        uint128 amountWei
    ) external nonReentrant {
        require(destination != address(0) && destination != address(this), "Invalid dest");
        require(amountWei > 0, "Amount must be > 0");

        Session storage s = sessions[msg.sender];
        require(s.active == 1, "Session revoked or expired");
        require(uint48(block.timestamp) < s.expiresAt, "Session expired");

        uint48 todayMidnight = uint48((block.timestamp / 1 days) * 1 days);
        if (s.lastResetTs < todayMidnight) {
            s.spentToday = 0;
            s.lastResetTs = todayMidnight;
        }

        uint128 remaining = s.dailyLimit - s.spentToday;
        require(amountWei <= remaining, "Daily limit exceeded");

        s.spentToday += amountWei;
        SafeERC20.safeTransfer(USDC, destination, amountWei);

        emit AgentSpent(msg.sender, sessionId, destination, amountWei, s.dailyLimit - s.spentToday);
    }

    function revoke(address agentKey) external onlyOwner {
        require(sessions[agentKey].active == 1, "Session inactive");
        sessions[agentKey].active = 0;
        emit SessionRevoked(agentKey);
    }

    function getSession(address agentKey) external view returns (
        uint128 dailyLimit,
        uint128 spentToday,
        uint128 remaining,
        uint48 expiresAt,
        bool active
    ) {
        Session storage s = sessions[agentKey];
        uint48 todayMidnight = uint48((block.timestamp / 1 days) * 1 days);
        bool isToday = s.lastResetTs >= todayMidnight;
        uint128 effectiveSpent = isToday ? s.spentToday : 0;

        dailyLimit = s.dailyLimit;
        spentToday = effectiveSpent;
        remaining = s.dailyLimit - effectiveSpent;
        expiresAt = s.expiresAt;
        active = s.active == 1 && uint48(block.timestamp) < s.expiresAt;
    }
}
