// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/**
 * @title EscrowSimple
 * @notice Simple escrow for agent-mediated payments with timeout-based claims.
 *         USDC is used as the settlement token.
 */
contract EscrowSimple is ReentrancyGuard {
    using SafeERC20 for IERC20;

    /// @notice USDC on Base (6 decimals)
    IERC20 public constant USDC = IERC20(0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913);

    /// @notice An escrow agreement between buyer and seller
    struct Escrow {
        bytes32 sessionId;    // Associated session (0 if none)
        address seller;       // Seller who receives funds
        address buyer;        // Buyer who deposited funds
        uint128 amount;       // Escrowed amount in USDC (6 decimals)
        uint48  timeout;      // Unix timestamp after which seller can claim
        uint48  createdAt;    // Creation timestamp
        bool    claimed;      // Whether the escrow is resolved
        bool    refunded;     // Whether funds were refunded
    }

    /// @notice Escrow ID -> Escrow data
    mapping(uint256 => Escrow) public escrows;

    /// @notice Next escrow ID
    uint256 private _nextId;

    event EscrowCreated(uint256 escrowId, bytes32 sessionId, address seller, address buyer, uint128 amount, uint48 timeout);
    event EscrowReleased(uint256 escrowId, address to, uint128 amount);
    event EscrowRefunded(uint256 escrowId, address to, uint128 amount);
    event EscrowClaimed(uint256 escrowId, address seller, uint128 amount);

    /**
     * @notice Create a new escrow. Buyer must call this.
     * @param seller Address of the seller
     * @param amount Amount in USDC (6 decimals) to escrow
     * @param timeoutSeconds Seconds until seller can auto-claim
     * @return escrowId The new escrow identifier
     */
    function create(
        address seller,
        uint128 amount,
        uint48 timeoutSeconds
    ) external returns (uint256 escrowId) {
        require(seller != address(0), "Escrow: invalid seller");
        require(seller != msg.sender, "Escrow: buyer != seller");
        require(amount > 0, "Escrow: amount must be > 0");
        require(timeoutSeconds > 0, "Escrow: timeout must be > 0");

        _nextId++;
        escrowId = _nextId;

        // Pull USDC from buyer into this contract
        USDC.safeTransferFrom(msg.sender, address(this), amount);

        escrows[escrowId] = Escrow({
            sessionId: 0,
            seller: seller,
            buyer: msg.sender,
            amount: amount,
            timeout: uint48(block.timestamp) + timeoutSeconds,
            createdAt: uint48(block.timestamp),
            claimed: false,
            refunded: false
        });

        emit EscrowCreated(escrowId, 0, seller, msg.sender, amount, timeoutSeconds);
    }

    /**
     * @notice Create an escrow linked to a SessionGuard session.
     */
    function createForSession(
        bytes32 sessionId,
        address seller,
        uint128 amount,
        uint48 timeoutSeconds
    ) external returns (uint256 escrowId) {
        require(seller != address(0), "Escrow: invalid seller");
        require(seller != msg.sender, "Escrow: buyer != seller");
        require(amount > 0, "Escrow: amount must be > 0");
        require(timeoutSeconds > 0, "Escrow: timeout must be > 0");

        _nextId++;
        escrowId = _nextId;

        USDC.safeTransferFrom(msg.sender, address(this), amount);

        escrows[escrowId] = Escrow({
            sessionId: sessionId,
            seller: seller,
            buyer: msg.sender,
            amount: amount,
            timeout: uint48(block.timestamp) + timeoutSeconds,
            createdAt: uint48(block.timestamp),
            claimed: false,
            refunded: false
        });

        emit EscrowCreated(escrowId, sessionId, seller, msg.sender, amount, timeoutSeconds);
    }

    /**
     * @notice Release escrowed funds to the seller. Can be called by anyone
     *         (typically the buyer confirming work is done).
     * @param escrowId The escrow identifier
     */
    function release(uint256 escrowId) external nonReentrant {
        Escrow storage e = escrows[escrowId];
        require(e.amount > 0, "Escrow: escrow does not exist");
        require(!e.claimed, "Escrow: already resolved");
        require(!e.refunded, "Escrow: already refunded");

        e.claimed = true;
        USDC.safeTransfer(e.seller, e.amount);

        emit EscrowReleased(escrowId, e.seller, e.amount);
    }

    /**
     * @notice Refund escrowed funds back to the buyer. Only buyer can call.
     * @param escrowId  The escrow identifier
     */
    function refund(uint256 escrowId) external nonReentrant {
        Escrow storage e = escrows[escrowId];
        require(e.amount > 0, "Escrow: escrow does not exist");
        require(!e.claimed, "Escrow: already resolved");
        require(!e.refunded, "Escrow: already refunded");
        require(msg.sender == e.buyer, "Escrow: only buyer can refund");

        e.refunded = true;
        USDC.safeTransfer(e.buyer, e.amount);

        emit EscrowRefunded(escrowId, e.buyer, e.amount);
    }

    /**
     * @notice Seller auto-claims after timeout expires.
     * @param escrowId The escrow identifier
     */
    function claim(uint256 escrowId) external nonReentrant {
        Escrow storage e = escrows[escrowId];
        require(e.amount > 0, "Escrow: escrow does not exist");
        require(!e.claimed, "Escrow: already resolved");
        require(!e.refunded, "Escrow: already refunded");
        require(msg.sender == e.seller, "Escrow: only seller can claim");
        require(uint48(block.timestamp) >= e.timeout, "Escrow: timeout not reached");

        e.claimed = true;
        USDC.safeTransfer(e.seller, e.amount);

        emit EscrowClaimed(escrowId, e.seller, e.amount);
    }
}
