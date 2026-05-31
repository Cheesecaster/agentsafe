// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/**
 * @title EscrowSimple
 * @notice Simple escrow for x402 agent-to-agent payments.
 * @dev Funds are locked until service is delivered or timeout occurs.
 *      Supports Base Mainnet USDC.
 */
contract EscrowSimple is Ownable, ReentrancyGuard {

    struct Escrow {
        address buyer;
        address seller;
        uint256 amount;
        address token;
        bool active;
        uint256 releaseTime;
        uint256 createdAt;
    }

    mapping(bytes32 => Escrow) public escrows;
    
    IERC20 public immutable USDC;

    event EscrowCreated(bytes32 id, address buyer, address seller, uint256 amount);
    event FundsReleased(bytes32 id, address seller);
    event FundsRefunded(bytes32 id, address buyer);

    constructor(address _usdc) Ownable(msg.sender) {
        USDC = IERC20(_usdc);
    }

    /**
     * @notice Create an escrow for a service.
     * @param id Unique ID for the escrow (hash of order details).
     * @param seller Service provider address.
     * @param amount Amount of USDC to lock.
     * @param durationSeconds Time before buyer can refund if seller doesn't deliver.
     */
    function createEscrow(bytes32 id, address seller, uint256 amount, uint64 durationSeconds) external nonReentrant {
        require(amount > 0, "Amount must be > 0");
        require(escrows[id].buyer == address(0), "ID already used");

        // Transfer USDC from buyer to this contract
        require(USDC.transferFrom(msg.sender, address(this), amount), "Transfer failed");

        escrows[id] = Escrow({
            buyer: msg.sender,
            seller: seller,
            amount: amount,
            token: address(USDC),
            active: true,
            releaseTime: block.timestamp + durationSeconds,
            createdAt: block.timestamp
        });

        emit EscrowCreated(id, msg.sender, seller, amount);
    }

    /**
     * @notice Release funds to seller.
     * Callable by Buyer (approve) or Seller (claim).
     * If Seller claims, they must prove work or wait for timeout (implementation dependent).
     * Simplified: Buyer approves release.
     */
    function release(bytes32 id) external nonReentrant {
        Escrow storage e = escrows[id];
        require(e.active, "Not active");
        require(msg.sender == e.buyer, "Only buyer can release");

        e.active = false;
        USDC.transfer(e.seller, e.amount);
        emit FundsReleased(id, e.seller);
    }

    /**
     * @notice Refund to buyer after timeout.
     */
    function refund(bytes32 id) external nonReentrant {
        Escrow storage e = escrows[id];
        require(e.active, "Not active");
        require(msg.sender == e.buyer, "Only buyer can refund");
        require(block.timestamp > e.releaseTime, "Timeout not reached");

        e.active = false;
        USDC.transfer(e.buyer, e.amount);
        emit FundsRefunded(id, e.buyer);
    }

    /**
     * @notice Check status of an escrow.
     */
    function getEscrow(bytes32 id) external view returns (Escrow memory) {
        return escrows[id];
    }
}
