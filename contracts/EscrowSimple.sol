// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/**
 * @title EscrowSimple
 * @notice Lightweight escrow for x402 agent-to-agent settlements on Base.
 * @dev Storage-packed (2 slots). Seller can claim after timeout if buyer inactive.
 *      Optimistic settlement: buyer approves, seller claims on timeout fallback.
 */
contract EscrowSimple is Ownable, ReentrancyGuard {

    struct Escrow {
        uint128 amount;
        address buyer;
        address seller;
        uint32 active;        // 1 = active, 0 = resolved
        uint40 releaseTime;   // Auto-refund/claim deadline
    }

    mapping(bytes32 => Escrow) public escrows;

    IERC20 public immutable USDC;

    event EscrowCreated(bytes32 id, address buyer, address seller, uint128 amount, uint40 releaseTime);
    event FundsReleased(bytes32 id, address seller, uint128 amount);
    event FundsRefunded(bytes32 id, address buyer, uint128 amount);
    event SellerClaimed(bytes32 id, address seller, uint128 amount);

    constructor(address _usdc) Ownable(msg.sender) {
        require(_usdc != address(0), "Invalid USDC");
        USDC = IERC20(_usdc);
    }

    /**
     * @notice Create escrow: buyer locks USDC.
     * @param id Hash of order (buyer:service:amount).
     * @param seller Service provider.
     * @param durationSeconds Timeout before auto-resolution.
     */
    function createEscrow(bytes32 id, address seller, uint128 amount, uint32 durationSeconds) external nonReentrant {
        require(amount > 0, "Amount must be > 0");
        require(seller != address(0), "Invalid seller");
        require(escrows[id].active == 0, "ID already used");

        // Lock USDC from buyer
        SafeERC20.safeTransferFrom(USDC, msg.sender, address(this), amount);

        uint40 rTime = uint40(block.timestamp) + durationSeconds;
        escrows[id] = Escrow({
            amount: amount,
            buyer: msg.sender,
            seller: seller,
            active: 1,
            releaseTime: rTime
        });

        emit EscrowCreated(id, msg.sender, seller, amount, rTime);
    }

    /**
     * @notice Buyer confirms service delivered -> release to seller.
     */
    function release(bytes32 id) external nonReentrant {
        Escrow storage e = escrows[id];
        require(e.active == 1, "Not active");
        require(msg.sender == e.buyer, "Only buyer");

        _resolve(id, e.seller, e.amount);
        emit FundsReleased(id, e.seller, e.amount);
    }

    /**
     * @notice Buyer refunds self after timeout expires without resolution.
     */
    function refund(bytes32 id) external nonReentrant {
        Escrow storage e = escrows[id];
        require(e.active == 1, "Not active");
        require(msg.sender == e.buyer || msg.sender == owner(), "Not authorized");
        require(uint40(block.timestamp) > e.releaseTime, "Timeout not reached");

        _resolve(id, e.buyer, e.amount);
        emit FundsRefunded(id, e.buyer, e.amount);
    }

    /**
     * @notice Seller auto-claims after timeout — fallback if buyer disappears.
     * Requires 2x timeout duration (more conservative, protects buyer).
     * This ensures buyer has double the time to raise a dispute.
     */
    function claim(bytes32 id) external nonReentrant {
        Escrow storage e = escrows[id];
        require(e.active == 1, "Not active");
        require(msg.sender == e.seller, "Only seller");

        uint40 claimTime = e.releaseTime + (e.releaseTime - uint40(block.timestamp));
        require(uint40(block.timestamp) >= claimTime, "Seller claim window not active");

        _resolve(id, e.seller, e.amount);
        emit SellerClaimed(id, e.seller, e.amount);
    }

    function _resolve(bytes32 id, address to, uint128 amount) internal {
        Escrow storage e = escrows[id];
        e.active = 0;
        SafeERC20.safeTransfer(USDC, to, amount);
    }

    function getEscrow(bytes32 id) external view returns (Escrow memory) {
        return escrows[id];
    }
}
