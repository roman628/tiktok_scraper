#!/usr/bin/env python3
"""
Test Framework for robust_master_downloader.py
Validates functionality and ensures consistent output
"""

import os
import sys
import json
import toml
import time
import subprocess
import shutil
import hashlib
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

class TikTokDownloaderTestFramework:
    """Test framework for validating robust_master_downloader.py functionality"""
    
    def __init__(self, config_path: str = "test_config.toml", script_path: Optional[str] = None):
        """Initialize test framework with configuration"""
        self.config_path = config_path
        self.config = self.load_config()
        # Use provided script_path, or fall back to config default, or use the old default
        if script_path:
            self.script_path = script_path
        elif self.config.get('test', {}).get('default_script_path'):
            self.script_path = self.config['test']['default_script_path']
        else:
            self.script_path = "../robust_master_downloader.py"
        self.test_start_time = datetime.now()
        self.test_results = {
            "start_time": self.test_start_time.isoformat(),
            "config_file": config_path,
            "script_path": script_path,
            "tests_run": [],
            "summary": {}
        }
        self.setup_logging()
        
    def load_config(self) -> Dict:
        """Load test configuration from TOML file"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            config = toml.load(f)
        
        # Validate required fields
        if not config.get('tiktok', {}).get('ms_token'):
            print("⚠️  Warning: MS_TOKEN not configured in test_config.toml")
            print("    Comments extraction will be skipped during testing")
        
        return config
    
    def setup_logging(self):
        """Setup logging for test runs"""
        log_file = self.config['paths']['test_log_file']
        
        # Configure logging
        logging.basicConfig(
            level=logging.DEBUG if self.config['test']['verbose'] else logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, mode='w'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def prepare_test_environment(self):
        """Prepare clean test environment"""
        self.logger.info("=== Preparing Test Environment ===")
        
        # Create test output file (empty JSON array)
        test_output = self.config['paths']['test_output_file']
        with open(test_output, 'w') as f:
            json.dump([], f)
        
        # Ensure test URLs file exists
        if not os.path.exists(self.config['paths']['test_urls_file']):
            raise FileNotFoundError(f"Test URLs file not found: {self.config['paths']['test_urls_file']}")
        
        self.logger.info("Test environment prepared")
        
    def build_command(self) -> List[str]:
        """Build command to run the downloader script"""
        cmd = [
            sys.executable,
            self.script_path,
            "--from-file", self.config['paths']['test_urls_file'],
            "--json-output", self.config['paths']['test_output_file'],
            "--limit", str(self.config['test']['test_url_count']),
            "--batch-size", str(self.config['processing']['batch_size']),
            "--delay", str(self.config['processing']['delay']),
            "--max-comments", str(self.config['processing']['max_comments']),
            "--workers", str(self.config['processing']['workers'])
        ]
        
        # Add MS token if configured
        ms_token = self.config['tiktok']['ms_token']
        if ms_token and ms_token != "YOUR_MS_TOKEN_HERE":
            cmd.extend(["--ms-token", ms_token])
        
        # Add whisper options
        if self.config['processing']['use_whisper']:
            cmd.append("--whisper")
            if self.config['processing']['force_cpu']:
                cmd.append("--force-cpu")
        
        return cmd
    
    def run_downloader(self) -> Dict[str, Any]:
        """Run the downloader script and capture output"""
        self.logger.info(f"=== Running {os.path.basename(self.script_path)} ===")
        
        cmd = self.build_command()
        self.logger.info(f"Command: {' '.join(cmd)}")
        
        # Run the command
        start_time = time.time()
        result = {
            "command": ' '.join(cmd),
            "start_time": datetime.now().isoformat(),
            "stdout": [],
            "stderr": [],
            "return_code": None,
            "duration": 0,
            "error": None
        }
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Capture output in real-time
            stdout_lines = []
            stderr_lines = []
            
            # Read output with timeout
            timeout = self.config['test']['timeout_per_video'] * self.config['test']['test_url_count']
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                stdout_lines = stdout.splitlines() if stdout else []
                stderr_lines = stderr.splitlines() if stderr else []
                
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                stdout_lines = stdout.splitlines() if stdout else []
                stderr_lines = stderr.splitlines() if stderr else []
                result["error"] = "Process timed out"
                
            result["stdout"] = stdout_lines
            result["stderr"] = stderr_lines
            result["return_code"] = process.returncode
            
        except Exception as e:
            result["error"] = str(e)
            result["traceback"] = traceback.format_exc()
            self.logger.error(f"Error running downloader: {e}")
            
        finally:
            result["duration"] = time.time() - start_time
            result["end_time"] = datetime.now().isoformat()
            
            # Test output is already in test_output.json from --json-output flag
        
        return result
    
    def get_expected_values(self) -> Dict[str, Any]:
        """Define expected values for the test video"""
        # Expected values for https://www.tiktok.com/@redditstories9x/video/7444549378808941870
        return {
            "title": "What is the saddest thing you have heard a child say? #redditreadings...",
            "description": "What is the saddest thing you have heard a child say? #redditreadings #askreddit #reddit #redditstories #reddit_tiktok #fyp #redditstorytime",
            "duration": 245,
            "video_id": "7444549378808941870",
            "url": "https://www.tiktok.com/@redditstories9x/video/7444549378808941870",
            "uploader": "redditstories9x",
            "uploader_url": "https://www.tiktok.com/@redditstories9x",
            "view_count": 700000,  # Minimum expected
            "like_count": 80000,   # Minimum expected
            "comment_count": 150,   # Minimum expected
            "repost_count": 500,    # Minimum expected
            "upload_date": "20241204",
            "min_transcription_length": 1000,  # Minimum character count for transcription
            "min_comments_count": 5  # Minimum number of comments to extract
        }
    
    def validate_output(self) -> Dict[str, Any]:
        """Validate the output JSON file"""
        self.logger.info("=== Validating Output ===")
        
        validation_results = {
            "file_exists": False,
            "valid_json": False,
            "json_format_valid": False,
            "entries_count": 0,
            "expected_count": self.config['test']['test_url_count'],  # Will be adjusted based on unique URLs
            "entries_valid": [],
            "missing_fields": [],
            "validation_errors": [],
            "expected_values_validation": [],
            "json_format_errors": []
        }
        
        test_output = self.config['paths']['test_output_file']
        
        # Check file exists
        if not os.path.exists(test_output):
            validation_results["validation_errors"].append("Output file does not exist")
            return validation_results
        
        validation_results["file_exists"] = True
        
        # First, check for proper JSON formatting (missing commas between entries)
        try:
            with open(test_output, 'r') as f:
                content = f.read()
            
            # Check for common JSON formatting errors
            # Look for patterns like }\n{ which indicate missing comma
            import re
            missing_comma_pattern = r'}\s*\n\s*\{'
            missing_commas = re.findall(missing_comma_pattern, content)
            if missing_commas:
                validation_results["json_format_errors"].append(f"❌ Missing comma between JSON entries (found {len(missing_commas)} instances of '}}\n{{')")
                validation_results["validation_errors"].append(f"JSON format error: Missing commas between entries")
            
            # Try to parse the JSON
            data = json.loads(content)
            validation_results["valid_json"] = True
            validation_results["json_format_valid"] = len(missing_commas) == 0
            
        except json.JSONDecodeError as e:
            validation_results["validation_errors"].append(f"Invalid JSON: {e}")
            validation_results["json_format_errors"].append(f"❌ JSON parsing failed: {str(e)}")
            
            # Try to identify the specific line/column of the error
            if hasattr(e, 'lineno') and hasattr(e, 'colno'):
                validation_results["json_format_errors"].append(f"   Error at line {e.lineno}, column {e.colno}")
                
                # Extract context around the error
                lines = content.split('\n')
                if e.lineno <= len(lines):
                    start_line = max(0, e.lineno - 3)
                    end_line = min(len(lines), e.lineno + 2)
                    context_lines = []
                    for i in range(start_line, end_line):
                        if i == e.lineno - 1:  # Error line (0-indexed)
                            context_lines.append(f">>> Line {i+1}: {lines[i][:100]}..." if len(lines[i]) > 100 else f">>> Line {i+1}: {lines[i]}")
                        else:
                            context_lines.append(f"    Line {i+1}: {lines[i][:100]}..." if len(lines[i]) > 100 else f"    Line {i+1}: {lines[i]}")
                    validation_results["json_format_errors"].append("   Context:\n" + "\n".join(context_lines))
            
            return validation_results
        
        # Check if data is a list
        if not isinstance(data, list):
            validation_results["validation_errors"].append("Output is not a JSON array")
            return validation_results
        
        validation_results["entries_count"] = len(data)
        
        # Count unique URLs in test file to determine expected count
        test_urls_file = self.config['paths']['test_urls_file']
        unique_urls = set()
        total_urls = 0
        if os.path.exists(test_urls_file):
            with open(test_urls_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and line.startswith('http'):
                        total_urls += 1
                        unique_urls.add(line)
        
        unique_count = len(unique_urls)
        validation_results["expected_count"] = unique_count  # Update expected count based on unique URLs
        
        # Check for duplicate detection
        # Count actual unique video IDs in the output
        unique_video_ids = set()
        duplicate_entries = []
        for i, entry in enumerate(data):
            video_id = entry.get('video_id') or entry.get('url', '')
            if video_id in unique_video_ids:
                duplicate_entries.append({
                    "index": i,
                    "video_id": video_id,
                    "url": entry.get('url', 'N/A')
                })
            else:
                unique_video_ids.add(video_id)
        
        actual_unique_count = len(unique_video_ids)
        
        if total_urls > unique_count:
            # There are duplicate URLs in the input
            duplicates_in_input = total_urls - unique_count
            
            if len(duplicate_entries) == 0 and actual_unique_count == unique_count:
                validation_results["duplicate_detection"] = f"✅ PASS - {duplicates_in_input} duplicate URL(s) correctly skipped ({unique_count} unique entries from {total_urls} input URLs)"
            else:
                validation_results["duplicate_detection"] = f"❌ FAIL - Duplicate detection failed:"
                validation_results["duplicate_detection"] += f"\n   • Input: {total_urls} URLs ({unique_count} unique, {duplicates_in_input} duplicates)"
                validation_results["duplicate_detection"] += f"\n   • Output: {len(data)} entries ({actual_unique_count} unique videos)"
                
                if len(duplicate_entries) > 0:
                    validation_results["duplicate_detection"] += f"\n   • Found {len(duplicate_entries)} duplicate entries in output:"
                    for dup in duplicate_entries[:3]:  # Show first 3 duplicates
                        validation_results["duplicate_detection"] += f"\n     - Entry #{dup['index']}: {dup['url']}"
                    if len(duplicate_entries) > 3:
                        validation_results["duplicate_detection"] += f"\n     ... and {len(duplicate_entries) - 3} more duplicates"
                
                validation_results["validation_errors"].append(f"Duplicate detection failed: Expected {unique_count} unique entries, got {actual_unique_count} unique and {len(duplicate_entries)} duplicates")
        else:
            # No duplicates in input
            if len(duplicate_entries) > 0:
                validation_results["duplicate_detection"] = f"❌ FAIL - Found unexpected duplicates in output (no duplicates in input)"
                validation_results["validation_errors"].append(f"Found {len(duplicate_entries)} unexpected duplicate entries")
            else:
                validation_results["duplicate_detection"] = f"✅ PASS - No duplicates found (as expected)"
        
        # Get expected values for validation
        expected = self.get_expected_values()
        
        # Validate each entry
        required_fields = [
            "url", "video_id", "uploader", "description", "title",
            "like_count", "comment_count", "duration", "upload_date"
        ]
        
        optional_fields = [
            "transcription", "whisper_transcription", "subtitle",
            "top_comments", "comments_extracted", "repost_count",
            "view_count", "uploader_url"
        ]
        
        for i, entry in enumerate(data):
            entry_validation = {
                "index": i,
                "url": entry.get("url", ""),
                "has_required_fields": True,
                "missing_required": [],
                "has_optional": [],
                "field_types_valid": True,
                "type_errors": []
            }
            
            # Check required fields
            for field in required_fields:
                if field not in entry:
                    entry_validation["has_required_fields"] = False
                    entry_validation["missing_required"].append(field)
            
            # Check optional fields
            for field in optional_fields:
                if field in entry:
                    entry_validation["has_optional"].append(field)
            
            # Validate field types
            if "like_count" in entry and not isinstance(entry["like_count"], (int, float)):
                entry_validation["field_types_valid"] = False
                entry_validation["type_errors"].append(f"like_count should be numeric, got {type(entry['like_count']).__name__}")
            
            if "comment_count" in entry and not isinstance(entry["comment_count"], (int, float)):
                entry_validation["field_types_valid"] = False
                entry_validation["type_errors"].append(f"comment_count should be numeric, got {type(entry['comment_count']).__name__}")
            
            if "top_comments" in entry and not isinstance(entry["top_comments"], list):
                entry_validation["field_types_valid"] = False
                entry_validation["type_errors"].append(f"top_comments should be list, got {type(entry['top_comments']).__name__}")
            
            # Check transcription quality
            if "transcription" in entry or "whisper_transcription" in entry:
                transcription = entry.get("transcription") or entry.get("whisper_transcription", "")
                entry_validation["transcription_length"] = len(transcription)
                entry_validation["has_transcription"] = len(transcription) > 50
            else:
                entry_validation["has_transcription"] = False
                entry_validation["transcription_length"] = 0
            
            # Check comments extraction
            if "top_comments" in entry:
                entry_validation["comments_count"] = len(entry["top_comments"])
                entry_validation["has_comments"] = len(entry["top_comments"]) > 0
            else:
                entry_validation["comments_count"] = 0
                entry_validation["has_comments"] = False
            
            # Validate against expected values for the specific test video
            # Look for the expected test video by video_id
            expected_video_id = expected.get('video_id', '7444549378808941870')
            if entry.get('video_id') == expected_video_id:
                expected_validation = {
                    "exact_matches": {},
                    "threshold_checks": {},
                    "failures": []
                }
                
                # Exact string matches
                exact_match_fields = ["title", "description", "video_id", "url", "uploader", "uploader_url", "upload_date"]
                for field in exact_match_fields:
                    if field in expected and field in entry:
                        if str(entry[field]) == str(expected[field]):
                            expected_validation["exact_matches"][field] = "✅ PASS"
                        else:
                            expected_validation["exact_matches"][field] = f"❌ FAIL - Expected: {expected[field]}, Got: {entry.get(field)}"
                            expected_validation["failures"].append(f"{field} mismatch")
                
                # Exact integer match for duration
                if "duration" in entry and "duration" in expected:
                    if entry["duration"] == expected["duration"]:
                        expected_validation["exact_matches"]["duration"] = "✅ PASS"
                    else:
                        expected_validation["exact_matches"]["duration"] = f"❌ FAIL - Expected: {expected['duration']}, Got: {entry['duration']}"
                        expected_validation["failures"].append("duration mismatch")
                
                # Threshold checks (>=)
                threshold_fields = {
                    "view_count": expected.get("view_count", 0),
                    "like_count": expected.get("like_count", 0),
                    "comment_count": expected.get("comment_count", 0),
                    "repost_count": expected.get("repost_count", 0)
                }
                
                for field, min_value in threshold_fields.items():
                    if field in entry:
                        if entry[field] >= min_value:
                            expected_validation["threshold_checks"][field] = f"✅ PASS (>= {min_value})"
                        else:
                            expected_validation["threshold_checks"][field] = f"❌ FAIL - Expected >= {min_value}, Got: {entry[field]}"
                            expected_validation["failures"].append(f"{field} below threshold")
                
                # Transcription length check
                transcription = entry.get("whisper_transcription") or entry.get("transcription", "")
                if transcription:
                    trans_length = len(transcription)
                    if trans_length >= expected.get("min_transcription_length", 1000):
                        expected_validation["threshold_checks"]["transcription_length"] = f"✅ PASS ({trans_length} chars)"
                    else:
                        expected_validation["threshold_checks"]["transcription_length"] = f"❌ FAIL - Expected >= {expected.get('min_transcription_length', 1000)}, Got: {trans_length}"
                        expected_validation["failures"].append("transcription too short")
                else:
                    expected_validation["threshold_checks"]["transcription_length"] = "❌ FAIL - No transcription found"
                    expected_validation["failures"].append("no transcription")
                
                # Comments count check
                comments_count = len(entry.get("top_comments", []))
                min_comments = expected.get("min_comments_count", 5)
                if comments_count >= min_comments:
                    expected_validation["threshold_checks"]["comments_extracted"] = f"✅ PASS ({comments_count} comments)"
                else:
                    expected_validation["threshold_checks"]["comments_extracted"] = f"❌ FAIL - Expected >= {min_comments}, Got: {comments_count}"
                    expected_validation["failures"].append("insufficient comments")
                
                # Only set this once for the first matching entry
                if not validation_results.get("expected_values_validation"):
                    validation_results["expected_values_validation"] = expected_validation
                entry_validation["expected_values_check"] = len(expected_validation["failures"]) == 0
            
            validation_results["entries_valid"].append(entry_validation)
        
        # Summary statistics
        validation_results["summary"] = {
            "total_entries": len(data),
            "entries_with_all_required": sum(1 for e in validation_results["entries_valid"] if e["has_required_fields"]),
            "entries_with_transcription": sum(1 for e in validation_results["entries_valid"] if e["has_transcription"]),
            "entries_with_comments": sum(1 for e in validation_results["entries_valid"] if e["has_comments"]),
            "average_transcription_length": sum(e.get("transcription_length", 0) for e in validation_results["entries_valid"]) / len(data) if data else 0,
            "average_comments_per_video": sum(e.get("comments_count", 0) for e in validation_results["entries_valid"]) / len(data) if data else 0
        }
        
        return validation_results
    
    def check_logs_for_errors(self, run_result: Dict) -> Dict[str, Any]:
        """Analyze logs for errors and warnings"""
        self.logger.info("=== Analyzing Logs ===")
        
        log_analysis = {
            "errors": [],
            "warnings": [],
            "ms_token_issues": [],
            "network_errors": [],
            "processing_stats": {},
            "performance_metrics": {}
        }
        
        # Combine stdout and stderr for analysis
        all_output = run_result.get("stdout", []) + run_result.get("stderr", [])
        
        for line in all_output:
            # Check for errors (but ignore "Failed: 0" which is a success indicator)
            if ("ERROR" in line or "❌" in line or "Failed" in line) and "Failed: 0" not in line:
                log_analysis["errors"].append(line)
            
            # Check for warnings
            if "WARNING" in line or "⚠️" in line:
                log_analysis["warnings"].append(line)
            
            # Check for MS_TOKEN issues
            if "MS_TOKEN" in line or "ms_token" in line.lower():
                if "expired" in line.lower() or "invalid" in line.lower() or "failed" in line.lower():
                    log_analysis["ms_token_issues"].append(line)
            
            # Check for network errors
            if "timeout" in line.lower() or "connection" in line.lower() or "network" in line.lower():
                if "error" in line.lower() or "failed" in line.lower():
                    log_analysis["network_errors"].append(line)
            
            # Extract processing statistics
            if "✅ Processed" in line:
                log_analysis["processing_stats"]["success_count"] = log_analysis["processing_stats"].get("success_count", 0) + 1
            
            if "⏭️  Skipping" in line:
                log_analysis["processing_stats"]["skip_count"] = log_analysis["processing_stats"].get("skip_count", 0) + 1
            
            if "Memory usage:" in line:
                try:
                    memory = float(line.split(":")[-1].strip().replace("MB", ""))
                    if "max_memory" not in log_analysis["performance_metrics"]:
                        log_analysis["performance_metrics"]["max_memory"] = memory
                    else:
                        log_analysis["performance_metrics"]["max_memory"] = max(log_analysis["performance_metrics"]["max_memory"], memory)
                except:
                    pass
        
        return log_analysis
    
    def generate_test_report(self, run_result: Dict, validation_result: Dict, log_analysis: Dict):
        """Generate comprehensive test report"""
        self.logger.info("=== Generating Test Report ===")
        
        # Calculate test duration
        test_end_time = datetime.now()
        test_duration = (test_end_time - self.test_start_time).total_seconds()
        
        # Determine overall test status
        expected_validation = validation_result.get("expected_values_validation", {})
        expected_values_passed = len(expected_validation.get("failures", [])) == 0 if expected_validation else True
        
        test_passed = (
            run_result.get("return_code") == 0 and
            validation_result.get("valid_json", False) and
            validation_result.get("entries_count", 0) > 0 and
            len(log_analysis.get("errors", [])) == 0 and
            expected_values_passed
        )
        
        # Create comprehensive report
        report = {
            "test_execution": {
                "start_time": self.test_start_time.isoformat(),
                "end_time": test_end_time.isoformat(),
                "duration_seconds": test_duration,
                "config_file": self.config_path,
                "command": run_result.get("command", ""),
                "return_code": run_result.get("return_code"),
                "test_passed": test_passed
            },
            
            "configuration": {
                "urls_tested": self.config['test']['test_url_count'],
                "ms_token_configured": bool(self.config['tiktok']['ms_token'] and self.config['tiktok']['ms_token'] != "YOUR_MS_TOKEN_HERE"),
                "whisper_enabled": self.config['processing']['use_whisper'],
                "workers": self.config['processing']['workers'],
                "batch_size": self.config['processing']['batch_size']
            },
            
            "output_validation": {
                "file_exists": validation_result.get("file_exists"),
                "valid_json": validation_result.get("valid_json"),
                "json_format_valid": validation_result.get("json_format_valid", False),
                "json_format_errors": validation_result.get("json_format_errors", []),
                "entries_processed": validation_result.get("entries_count"),
                "entries_expected": validation_result.get("expected_count"),
                "duplicate_detection": validation_result.get("duplicate_detection", "N/A"),
                "all_required_fields_present": validation_result.get("summary", {}).get("entries_with_all_required") == validation_result.get("entries_count"),
                "transcription_coverage": f"{validation_result.get('summary', {}).get('entries_with_transcription', 0)}/{validation_result.get('entries_count', 0)}",
                "comments_coverage": f"{validation_result.get('summary', {}).get('entries_with_comments', 0)}/{validation_result.get('entries_count', 0)}",
                "avg_transcription_length": validation_result.get("summary", {}).get("average_transcription_length", 0),
                "avg_comments_per_video": validation_result.get("summary", {}).get("average_comments_per_video", 0)
            },
            
            "expected_values_validation": validation_result.get("expected_values_validation", {}),
            
            "log_analysis": {
                "error_count": len(log_analysis.get("errors", [])),
                "warning_count": len(log_analysis.get("warnings", [])),
                "ms_token_issues": len(log_analysis.get("ms_token_issues", [])),
                "network_errors": len(log_analysis.get("network_errors", [])),
                "videos_processed": log_analysis.get("processing_stats", {}).get("success_count", 0),
                "videos_skipped": log_analysis.get("processing_stats", {}).get("skip_count", 0),
                "max_memory_mb": log_analysis.get("performance_metrics", {}).get("max_memory", 0)
            },
            
            "detailed_results": {
                "validation_details": validation_result.get("entries_valid", []),
                "errors_encountered": log_analysis.get("errors", [])[:10],  # First 10 errors
                "warnings_encountered": log_analysis.get("warnings", [])[:10]  # First 10 warnings
            },
            
            "test_status": {
                "overall_result": "PASSED" if test_passed else "FAILED",
                "failure_reasons": []
            }
        }
        
        # Add failure reasons if test failed
        if not test_passed:
            if run_result.get("return_code") != 0:
                report["test_status"]["failure_reasons"].append(f"Process exited with code {run_result.get('return_code')}")
            
            if not validation_result.get("valid_json"):
                report["test_status"]["failure_reasons"].append("Output JSON is invalid")
            
            if validation_result.get("entries_count", 0) == 0:
                report["test_status"]["failure_reasons"].append("No entries were processed")
            
            if len(log_analysis.get("errors", [])) > 0:
                report["test_status"]["failure_reasons"].append(f"Found {len(log_analysis.get('errors', []))} errors in logs")
            
            if not expected_values_passed:
                failures = expected_validation.get("failures", [])
                report["test_status"]["failure_reasons"].append(f"Expected values validation failed: {', '.join(failures)}")
        
        # Save report to file
        report_file = self.config['paths']['test_report_file']
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.logger.info(f"Test report saved to: {report_file}")
        
        # Print summary to console
        self.print_test_summary(report)
        
        return report
    
    def print_test_summary(self, report: Dict):
        """Print a human-readable test summary"""
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        status = report["test_status"]["overall_result"]
        status_symbol = "✅" if status == "PASSED" else "❌"
        print(f"\n{status_symbol} Overall Result: {status}")
        
        print(f"\n📊 Statistics:")
        print(f"  • Duration: {report['test_execution']['duration_seconds']:.1f} seconds")
        print(f"  • URLs Tested: {report['configuration']['urls_tested']}")
        print(f"  • Videos Processed: {report['log_analysis']['videos_processed']}")
        print(f"  • Videos Skipped: {report['log_analysis']['videos_skipped']}")
        
        print(f"\n📝 Output Validation:")
        print(f"  • Valid JSON: {'✅' if report['output_validation']['valid_json'] else '❌'}")
        print(f"  • JSON Format: {'✅ Valid' if report['output_validation'].get('json_format_valid', True) else '❌ Invalid (missing commas between entries)'}")
        print(f"  • Entries Processed: {report['output_validation']['entries_processed']}/{report['output_validation']['entries_expected']}")
        print(f"  • Transcription Coverage: {report['output_validation']['transcription_coverage']}")
        print(f"  • Comments Coverage: {report['output_validation']['comments_coverage']}")
        
        # Show duplicate detection result if applicable
        dup_detection = report['output_validation'].get('duplicate_detection', 'N/A')
        if dup_detection != 'N/A':
            if "PASS" in dup_detection:
                print(f"  • Duplicate Detection: ✅ PASSED")
            else:
                print(f"  • Duplicate Detection: ❌ FAILED")
                # Print details if failed
                for line in dup_detection.split('\n')[1:]:
                    print(f"    {line}")
        
        # Show JSON format errors if any
        if report['output_validation'].get('json_format_errors'):
            print(f"\n❌ JSON Format Errors:")
            for error in report['output_validation']['json_format_errors'][:3]:  # Show first 3 errors
                print(f"  {error}")
        
        print(f"\n⚠️  Issues:")
        print(f"  • Errors: {report['log_analysis']['error_count']}")
        print(f"  • Warnings: {report['log_analysis']['warning_count']}")
        print(f"  • Network Errors: {report['log_analysis']['network_errors']}")
        
        # Show expected values validation results
        ev = report.get("expected_values_validation", {})
        if ev:
            failures = ev.get("failures", [])
            if len(failures) == 0:
                print(f"\n✅ Expected Values Validation: PASSED")
            else:
                print(f"\n❌ Expected Values Validation: FAILED")
                print(f"  Failures: {', '.join(failures)}")
            
            # Show details
            if ev.get("exact_matches"):
                print("\n  📋 Exact Match Tests:")
                for field, result in ev["exact_matches"].items():
                    if "PASS" in result:
                        print(f"    • {field}: ✅")
                    else:
                        # Extract expected vs actual from the result string
                        print(f"    • {field}: ❌")
                        if "Expected:" in result:
                            print(f"      {result.split(' - ')[1]}")
            
            if ev.get("threshold_checks"):
                print("\n  📊 Threshold Tests:")
                for field, result in ev["threshold_checks"].items():
                    if "PASS" in result:
                        print(f"    • {field}: ✅ {result}")
                    else:
                        print(f"    • {field}: ❌")
                        if "Expected" in result:
                            print(f"      {result.split(' - ')[1]}")
        
        if report["test_status"]["failure_reasons"]:
            print(f"\n❌ Failure Reasons:")
            for reason in report["test_status"]["failure_reasons"]:
                print(f"  • {reason}")
            
            # Show actual errors if any
            if report["log_analysis"]["error_count"] > 0:
                errors = report.get("detailed_results", {}).get("errors_encountered", [])
                if errors:
                    print(f"\n  Actual errors found:")
                    for error in errors[:5]:  # Show first 5 errors
                        print(f"    - {error}")
        
        print(f"\n💾 Test Artifacts:")
        print(f"  • Log File: {self.config['paths']['test_log_file']}")
        print(f"  • Output File: {self.config['paths']['test_output_file']}")
        print(f"  • Report File: {self.config['paths']['test_report_file']}")
        
        print("\n" + "="*60)
    
    def cleanup(self):
        """Clean up test artifacts if configured"""
        if self.config['test'].get('cleanup_after_test', False):
            self.logger.info("Cleaning up test artifacts...")
            
            # Remove test files
            test_files = [
                self.config['paths']['test_output_file'],
                self.config['paths']['test_log_file'],
                "download_progress.json"
            ]
            
            for file in test_files:
                if os.path.exists(file):
                    os.remove(file)
                    self.logger.info(f"Removed {file}")
            
            # Remove downloads directory if created
            if os.path.exists("downloads"):
                shutil.rmtree("downloads")
                self.logger.info("Removed downloads directory")
    
    def run_tests(self):
        """Main test execution method"""
        try:
            script_name = os.path.basename(self.script_path)
            print(f"\n🚀 Starting TikTok Downloader Test Framework")
            print(f"   Testing: {script_name}")
            print("="*60)
            
            # Prepare environment
            self.prepare_test_environment()
            
            # Run the downloader
            run_result = self.run_downloader()
            
            # Wait a moment for file writes to complete
            time.sleep(2)
            
            # Validate output
            validation_result = self.validate_output()
            
            # Analyze logs
            log_analysis = self.check_logs_for_errors(run_result)
            
            # Generate report
            report = self.generate_test_report(run_result, validation_result, log_analysis)
            
            # Cleanup if configured
            self.cleanup()
            
            # Return success/failure
            return report["test_status"]["overall_result"] == "PASSED"
            
        except Exception as e:
            self.logger.error(f"Test framework error: {e}")
            self.logger.error(traceback.format_exc())
            return False


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test framework for TikTok downloader scripts")
    parser.add_argument("--config", default="test_config.toml", help="Path to test configuration file")
    parser.add_argument("--cleanup", action="store_true", help="Clean up test artifacts after completion")
    parser.add_argument("--with", dest="script_path", default=None, 
                        help="Path to the script to test (overrides config default)")
    
    args = parser.parse_args()
    
    # Override cleanup setting if provided via command line
    if args.cleanup:
        # Temporarily modify config
        import toml
        with open(args.config, 'r') as f:
            config = toml.load(f)
        config['test']['cleanup_after_test'] = True
        
    # Run tests - pass script_path only if provided via --with
    tester = TikTokDownloaderTestFramework(args.config, args.script_path)
    success = tester.run_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()