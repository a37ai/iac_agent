#!/usr/bin/env python3
import os
import pty
import select
import sys
import termios
import tty
import subprocess
import fcntl
import time
import signal
from termcolor import colored
from typing import Optional

class ToolResult:
    def __init__(self, status: str, output: Optional[str] = None, error: Optional[str] = None):
        self.status = status
        self.output = output
        self.error = error

def execute_command(cmd: str, timeout: int = 5) -> ToolResult:
    """
    Execute the command `cmd` in a pseudoterminal so that interactive input is handled
    according to the child process’s terminal settings. If the child process disables echo
    (for example, during a password prompt), then the inactivity timeout is not enforced
    and the process will wait indefinitely for input.
    """
    output_buffer = []
    # Initialize the inactivity timer.
    start_time = time.time()
    
    # Save the original terminal settings for sys.stdin.
    orig_term_settings = termios.tcgetattr(sys.stdin.fileno())
    try:
        # Set sys.stdin to raw mode so that input is captured immediately.
        tty.setraw(sys.stdin.fileno())
        
        # Create a pseudoterminal pair.
        master_fd, slave_fd = os.openpty()
        # Duplicate the slave fd so that we can query its terminal attributes without interfering
        # with the child process’s controlling terminal.
        slave_fd_dup = os.dup(slave_fd)
        
        # Spawn the subprocess with the slave fd as its stdin, stdout, and stderr.
        # preexec_fn=os.setsid gives the child its own process group.
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=os.setsid
        )
        
        # We no longer need the original slave fd in the parent.
        os.close(slave_fd)
        
        # Set the master file descriptor to non-blocking mode.
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        while True:
            # If the process has terminated, exit the loop.
            if process.poll() is not None:
                break

            now = time.time()
            # Query the slave's terminal attributes to check whether echo is enabled.
            try:
                slave_attrs = termios.tcgetattr(slave_fd_dup)
                # The terminal’s local flags are at index 3. If termios.ECHO is set, echo is enabled.
                echo_enabled = bool(slave_attrs[3] & termios.ECHO)
            except Exception:
                # In the event of an error, default to enforcing the timeout.
                echo_enabled = True
            
            # Enforce the timeout only if echo is enabled.
            # If echo is disabled (e.g. during a password prompt), we wait indefinitely.
            if echo_enabled and timeout and (now - start_time) > timeout:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                return ToolResult("error", error=f"Command timed out after {timeout} seconds")

            # Wait for input from either the child (master_fd) or the user (sys.stdin).
            ready_fds, _, _ = select.select([master_fd, sys.stdin], [], [], 0.1)
            for fd in ready_fds:
                if fd == master_fd:
                    # Read output from the child process.
                    try:
                        data = os.read(master_fd, 1024)
                    except OSError:
                        data = b""
                    if data:
                        decoded = data.decode(errors="ignore")
                        sys.stdout.write(decoded)
                        sys.stdout.flush()
                        output_buffer.append(decoded)
                elif fd == sys.stdin:
                    try:
                        # Read user input from sys.stdin. In raw mode this may be character-by-character.
                        user_input = os.read(sys.stdin.fileno(), 1024)
                        if user_input:
                            os.write(master_fd, user_input)
                            # Reset the inactivity timer on user input.
                            start_time = time.time()
                    except OSError:
                        pass
    finally:
        # Restore the original terminal settings.
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, orig_term_settings)
        # Close the file descriptors.
        try:
            os.close(master_fd)
        except Exception:
            pass
        try:
            os.close(slave_fd_dup)
        except Exception:
            pass

    # Allow a short time for any remaining output to be flushed.
    try:
        process.wait(timeout=0.1)
    except subprocess.TimeoutExpired:
        pass

    retcode = process.poll()
    return ToolResult(
        "success" if retcode == 0 else "error",
        output="".join(output_buffer),
        error=f"Command failed with exit code {retcode}" if retcode != 0 else None
    )

if __name__ == "__main__":
    # Test commands. Commands that disable echo (such as sudo) will now wait indefinitely for input.
    commands = [
        "ls -la",
        "echo 'hello world'",
        "sudo ls /var/root",
        "sudo pip3 install numpy",
        "python3 -c 'print(input(\"Enter something: \"))'",
        "cd /tmp",  # For testing non-interactive commands.
        ("cd /path/to/repo && echo 'guessWhat3#' | ansible-playbook prometheus_playbook.yml "
         "--ask-become-pass")
    ]
    
    for cmd in commands:
        print(f"\nTesting command: {cmd}")
        result = execute_command(cmd)
        print(f"\nStatus: {result.status}")
        if result.output:
            print(f"\nOutput: {result.output}")
        if result.error:
            print(f"\nError: {result.error}")
